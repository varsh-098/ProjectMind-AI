"""
backend/llm/router.py
======================
Phase 21 — Resilient Multi-Provider LLM Router with Automatic Failover.

PURPOSE:
    Upgrades ProjectMind's static factory into a resilient, self-healing
    LLM abstraction layer with:
      1. Automatic Fallback: If primary provider fails (offline, rate limit, timeout),
         automatically fails over to secondary providers (e.g. Nemotron -> Groq -> Gemini).
      2. Health Probing: Real-time latency and online/offline status for all providers.
      3. Dynamic Switching: Switch active provider or fallback chain at runtime without restart.
      4. Sync & Async Support: Drop-in compatibility for async routes and sync agents.
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional

try:
    import httpx
    _CONNECT_ERRORS = (httpx.ConnectError, ConnectionError)
    _TIMEOUT_ERRORS = (httpx.TimeoutException, TimeoutError)
    _HTTP_STATUS_ERROR = (httpx.HTTPStatusError,)
except ImportError:
    httpx = None
    _CONNECT_ERRORS = (ConnectionError,)
    _TIMEOUT_ERRORS = (TimeoutError,)
    _HTTP_STATUS_ERROR = ()

from backend.config import settings
from backend.llm.base import BaseLLMProvider

logger = logging.getLogger("projectmind.llm.router")


class ResilientLLMProvider(BaseLLMProvider):
    """
    Self-healing LLM provider that wraps concrete providers in an automatic
    failover chain. Implements BaseLLMProvider.
    """

    SUPPORTED_PROVIDERS = ["groq", "gemini", "nemotron"]

    def __init__(
        self,
        active_provider: Optional[str] = None,
        fallback_chain: Optional[List[str]] = None,
        model_overrides: Optional[Dict[str, str]] = None,
        active_tier: Optional[str] = None,
    ):
        self._active_provider = (
            active_provider or getattr(settings, "llm_provider", "groq")
        ).lower()

        # Default fallback chain: prioritize configured active provider, then others
        if fallback_chain:
            self._fallback_chain = [p.lower() for p in fallback_chain]
        else:
            default_chain = [self._active_provider]
            for p in self.SUPPORTED_PROVIDERS:
                if p not in default_chain:
                    default_chain.append(p)
            self._fallback_chain = default_chain

        self._model_overrides: Dict[str, str] = {
            k.lower(): v for k, v in (model_overrides or {}).items()
        }
        self._active_tier = active_tier
        self._provider_instances: Dict[str, BaseLLMProvider] = {}
        self.last_execution_meta: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Lazy Provider Instantiation
    # ------------------------------------------------------------------

    def get_concrete_provider(
        self,
        name: str,
        model: Optional[str] = None,
    ) -> Optional[BaseLLMProvider]:
        """
        Lazily instantiate concrete providers. Avoids crashing at startup
        if one provider's optional API key is not yet set in .env.
        Supports model-specific caching.
        """
        clean_name = name.strip().lower()
        target_model = model or self._model_overrides.get(clean_name)
        cache_key = f"{clean_name}:{target_model}" if target_model else clean_name

        if cache_key in self._provider_instances:
            return self._provider_instances[cache_key]

        try:
            if clean_name == "nemotron":
                from backend.llm.nemotron import NemotronProvider
                provider = NemotronProvider(model=target_model)
            elif clean_name == "groq":
                from backend.llm.groq_provider import GroqProvider
                provider = GroqProvider(model=target_model)
            elif clean_name == "gemini":
                from backend.llm.gemini_provider import GeminiProvider
                provider = GeminiProvider(model=target_model)
            else:
                return None

            self._provider_instances[cache_key] = provider
            return provider

        except Exception as e:
            logger.warning(f"Could not initialize provider '{clean_name}': {e}")
            return None

    # ------------------------------------------------------------------
    # Dynamic Configuration
    # ------------------------------------------------------------------

    def set_active_provider(self, name: str) -> None:
        """Switch active primary provider dynamically."""
        clean = name.strip().lower()
        if clean not in self.SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unknown provider '{name}'. Supported: {self.SUPPORTED_PROVIDERS}"
            )
        self._active_provider = clean
        # Move active provider to front of fallback chain
        new_chain = [clean] + [p for p in self._fallback_chain if p != clean]
        self._fallback_chain = new_chain

    def set_fallback_chain(self, chain: List[str]) -> None:
        """Update failover priority order."""
        cleaned = [p.strip().lower() for p in chain]
        for p in cleaned:
            if p not in self.SUPPORTED_PROVIDERS:
                raise ValueError(
                    f"Unknown provider '{p}' in chain. Supported: {self.SUPPORTED_PROVIDERS}"
                )
        self._fallback_chain = cleaned
        if cleaned:
            self._active_provider = cleaned[0]

    def get_config(self) -> Dict[str, Any]:
        """Return current router state."""
        return {
            "active_provider": self._active_provider,
            "fallback_chain": list(self._fallback_chain),
            "supported_providers": list(self.SUPPORTED_PROVIDERS),
            "active_tier": self._active_tier,
            "model_overrides": dict(self._model_overrides),
            "last_execution": self.last_execution_meta,
        }

    # ------------------------------------------------------------------
    # Health Probing
    # ------------------------------------------------------------------

    async def check_health(self) -> Dict[str, Any]:
        """
        Probe all supported providers concurrently and return status report.
        """
        results = {}
        for p_name in self.SUPPORTED_PROVIDERS:
            provider = self.get_concrete_provider(p_name)
            if not provider:
                results[p_name] = {
                    "status": "unconfigured",
                    "error": "Missing credentials or initialization failure",
                }
                continue

            try:
                res = await provider.health_check()
                results[p_name] = res
            except Exception as e:
                results[p_name] = {
                    "status": "offline",
                    "error": str(e),
                }

        return {
            "router_active": self._active_provider,
            "fallback_chain": self._fallback_chain,
            "providers": results,
        }

    # ------------------------------------------------------------------
    # Resilient Chat with Automatic Failover & Tier Specialization
    # ------------------------------------------------------------------

    async def chat(
        self,
        message: str,
        system_instruction: Optional[str] = None,
        tier: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> str:
        """
        Execute chat request across the fallback chain with automatic failover,
        optionally routing via a specialized task tier.
        """
        effective_tier = tier
        if not effective_tier and task_type:
            from backend.llm.model_registry import model_registry
            effective_tier = model_registry.get_tier_for_task(task_type)

        tier_profile = None
        if effective_tier:
            from backend.llm.model_registry import model_registry
            tier_profile = model_registry.get_profile(effective_tier)

        if tier_profile:
            active = tier_profile.provider
            chain = [active]
            for p in tier_profile.fallback_chain:
                if p not in chain:
                    chain.append(p)
            model_target = tier_profile.model_name
        else:
            active = self._active_provider
            chain = self._fallback_chain
            model_target = self._model_overrides.get(active)

        attempts = []
        order = [active]
        for p in chain:
            if p not in order:
                order.append(p)

        for provider_name in order:
            chosen_model = (
                model_target if (tier_profile and provider_name == tier_profile.provider)
                else self._model_overrides.get(provider_name)
            )
            provider = self.get_concrete_provider(provider_name, model=chosen_model)
            if not provider:
                attempts.append({
                    "provider": provider_name,
                    "status": "skipped",
                    "error": "Unconfigured or missing credentials",
                })
                continue

            t0 = time.perf_counter()
            try:
                response = await provider.chat(
                    message=message,
                    system_instruction=system_instruction,
                )
                latency_ms = round((time.perf_counter() - t0) * 1000, 1)

                self.last_execution_meta = {
                    "provider_used": provider_name,
                    "model_used": getattr(provider, "model", chosen_model),
                    "tier_used": effective_tier or self._active_tier,
                    "task_type": task_type,
                    "latency_ms": latency_ms,
                    "fallbacks_attempted": attempts,
                    "success": True,
                }
                return response

            except _CONNECT_ERRORS as e:
                attempts.append({
                    "provider": provider_name,
                    "error": f"Connection refused / Server down: {e}",
                })
            except _TIMEOUT_ERRORS as e:
                attempts.append({
                    "provider": provider_name,
                    "error": f"Request timed out: {e}",
                })
            except _HTTP_STATUS_ERROR as e:
                attempts.append({
                    "provider": provider_name,
                    "error": f"HTTP {getattr(e.response, 'status_code', 'error')}: {getattr(e.response, 'text', '')[:120]}",
                })
            except Exception as e:
                attempts.append({
                    "provider": provider_name,
                    "error": f"{type(e).__name__}: {e}",
                })

        # If we reach here, all providers failed
        self.last_execution_meta = {
            "provider_used": None,
            "tier_used": effective_tier or self._active_tier,
            "task_type": task_type,
            "fallbacks_attempted": attempts,
            "success": False,
        }

        error_details = "\n".join(
            [f"  - {a['provider']}: {a['error']}" for a in attempts]
        )
        raise RuntimeError(
            f"All LLM providers in fallback chain failed:\n{error_details}"
        )

    def chat_sync(
        self,
        message: str,
        system_instruction: Optional[str] = None,
        tier: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> str:
        """
        Synchronous wrapper for BaseAgent / non-async call sites.
        Safely bridges to the failover chain.
        """
        coro = self.chat(
            message,
            system_instruction=system_instruction,
            tier=tier,
            task_type=task_type,
        )
        try:
            coro.send(None)
        except StopIteration as e:
            return e.value


# Global default router singleton
default_llm_router = ResilientLLMProvider()
