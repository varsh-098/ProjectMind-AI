"""
tests/test_multi_model.py
==========================
Unit tests for Phase 22: Multiple Model Support & Task-to-Model Specialization.

Tests:
  1. ModelTier enum and ModelProfile registration & copying.
  2. Task-to-Tier resolution (routing -> fast, coding -> complex, etc.).
  3. Dynamic tier configuration updates & task remapping.
  4. Provider resolution by tier and task type via ModelRegistry & factory.
  5. Resilient tier-aware chat execution & failover metadata.
  6. Supervisor dynamic tier specialization.
  7. AgentBuilder & AgentSpec model_tier support.
  8. FastAPI tier endpoints (/llm/tiers, /llm/tiers/configure, /llm/tiers/route).
"""

import unittest
from unittest.mock import MagicMock, AsyncMock, patch

from backend.llm.model_registry import (
    ModelTier,
    ModelProfile,
    ModelRegistry,
    DEFAULT_TASK_MAPPINGS,
)
from backend.llm.base import BaseLLMProvider
from backend.llm.factory import get_llm_provider, get_tier_provider
from backend.llm.router import ResilientLLMProvider
from backend.supervisor.supervisor import Supervisor
from backend.agents.builder import AgentSpec, AgentBuilder, STARTER_TEMPLATES


def run_coro(coro):
    """
    Safely drive a pure coroutine in the Windows sandbox environment
    without spawning Proactor event loop sockets.
    """
    try:
        coro.send(None)
    except StopIteration as e:
        return e.value


class MockLLM(BaseLLMProvider):
    """Predictable mock provider for testing tier routing."""

    def __init__(self, response_text: str = "Mock response", model: str = "mock-model"):
        self.response_text = response_text
        self.model = model
        self.chat_calls = []

    async def chat(self, message: str, system_instruction: str = None) -> str:
        self.chat_calls.append({"message": message, "system_instruction": system_instruction})
        return self.response_text


class TestModelRegistry(unittest.TestCase):
    """Tests for ModelRegistry, ModelTier, and Task Mapping."""

    def setUp(self):
        self.registry = ModelRegistry()

    def test_default_tiers_loaded(self):
        """Verify all 4 standard tiers are initialized with proper configurations."""
        tiers = self.registry.list_tiers()
        tier_names = {t["tier"] for t in tiers}
        self.assertEqual(tier_names, {"fast", "balanced", "complex", "local"})

        fast_profile = self.registry.get_profile(ModelTier.FAST)
        self.assertIsNotNone(fast_profile)
        self.assertIn(fast_profile.provider, ["groq", "gemini", "nemotron"])
        self.assertTrue(len(fast_profile.fallback_chain) >= 1)

    def test_task_to_tier_resolution(self):
        """Verify standard tasks resolve to expected model tiers."""
        self.assertEqual(self.registry.get_tier_for_task("routing"), "fast")
        self.assertEqual(self.registry.get_tier_for_task("classification"), "fast")
        self.assertEqual(self.registry.get_tier_for_task("coding"), "complex")
        self.assertEqual(self.registry.get_tier_for_task("refactoring"), "complex")
        self.assertEqual(self.registry.get_tier_for_task("review"), "balanced")
        self.assertEqual(self.registry.get_tier_for_task("testing"), "balanced")
        self.assertEqual(self.registry.get_tier_for_task("local"), "local")
        self.assertEqual(self.registry.get_tier_for_task("offline"), "local")
        # Unknown tasks default to balanced
        self.assertEqual(self.registry.get_tier_for_task("unknown_custom_task"), "balanced")

    def test_map_custom_task(self):
        """Verify adding and updating custom task-to-tier mappings."""
        self.registry.map_task("sql_optimization", ModelTier.COMPLEX)
        self.assertEqual(self.registry.get_tier_for_task("sql_optimization"), "complex")

        # Remap existing task
        self.registry.map_task("review", ModelTier.COMPLEX)
        self.assertEqual(self.registry.get_tier_for_task("review"), "complex")

    def test_invalid_task_mapping_tier(self):
        """Verify mapping to non-existent tier raises ValueError."""
        with self.assertRaises(ValueError):
            self.registry.map_task("dummy", "quantum_tier")

    def test_update_tier_profile(self):
        """Verify updating a tier's provider, model, and fallback chain."""
        updated = self.registry.update_profile(
            tier="complex",
            provider="groq",
            model_name="llama-3.3-70b-versatile",
            fallback_chain=["groq", "gemini"],
            temperature=0.2,
        )
        self.assertEqual(updated.provider, "groq")
        self.assertEqual(updated.model_name, "llama-3.3-70b-versatile")
        self.assertEqual(updated.fallback_chain, ["groq", "gemini"])
        self.assertEqual(updated.temperature, 0.2)

        # Confirm registry persisted the change
        stored = self.registry.get_profile("complex")
        self.assertEqual(stored.model_name, "llama-3.3-70b-versatile")

    def test_update_unknown_tier_raises_keyerror(self):
        """Updating an unknown tier raises KeyError."""
        with self.assertRaises(KeyError):
            self.registry.update_profile(tier="non_existent", provider="groq")

    def test_get_profile_isolation(self):
        """Ensure get_profile returns a deep copy that cannot mutate internal state."""
        prof = self.registry.get_profile("fast")
        prof.fallback_chain.append("unauthorized_provider")
        stored = self.registry.get_profile("fast")
        self.assertNotIn("unauthorized_provider", stored.fallback_chain)


class TestTierProviderResolution(unittest.TestCase):
    """Tests for provider instantiation from tiers and factory."""

    def setUp(self):
        self.registry = ModelRegistry()

    def test_get_provider_for_tier_resilient(self):
        """Verify get_provider_for_tier returns ResilientLLMProvider tuned for tier."""
        provider = self.registry.get_provider_for_tier(ModelTier.COMPLEX, resilient=True)
        self.assertIsInstance(provider, ResilientLLMProvider)
        config = provider.get_config()
        self.assertEqual(config["active_tier"], "complex")
        self.assertIn("gemini", config["fallback_chain"])

    def test_get_provider_for_task(self):
        """Verify get_provider_for_task maps task to tier and returns provider."""
        provider = self.registry.get_provider_for_task("routing")
        self.assertIsInstance(provider, ResilientLLMProvider)
        self.assertEqual(provider.get_config()["active_tier"], "fast")

    def test_factory_get_llm_provider_by_tier(self):
        """Verify get_llm_provider('complex') routes to tier provider."""
        provider = get_llm_provider("complex")
        self.assertIsInstance(provider, ResilientLLMProvider)
        self.assertEqual(provider.get_config()["active_tier"], "complex")

    def test_factory_get_tier_provider_helper(self):
        """Verify get_tier_provider helper routes by task name."""
        provider = get_tier_provider("coding")
        self.assertIsInstance(provider, ResilientLLMProvider)
        self.assertEqual(provider.get_config()["active_tier"], "complex")


class TestRouterTierExecution(unittest.TestCase):
    """Tests for resilient router tier-aware execution and trace recording."""

    def test_router_chat_with_explicit_tier(self):
        """Test chat() with tier parameter uses tier configuration and records metadata."""
        router = ResilientLLMProvider()
        mock_gemini = MockLLM(response_text="Gemini Pro Solution", model="gemini-2.5-pro")

        # Mock concrete provider loader
        def mock_loader(name, model=None):
            if name == "gemini":
                return mock_gemini
            return None

        router.get_concrete_provider = mock_loader

        response = run_coro(router.chat("Implement quicksort", tier="complex"))
        self.assertEqual(response, "Gemini Pro Solution")
        meta = router.last_execution_meta
        self.assertEqual(meta["tier_used"], "complex")
        self.assertEqual(meta["model_used"], "gemini-2.5-pro")
        self.assertEqual(meta["provider_used"], "gemini")
        self.assertTrue(meta["success"])

    def test_router_chat_with_task_type(self):
        """Test chat() with task_type parameter resolves tier automatically."""
        router = ResilientLLMProvider()
        mock_groq = MockLLM(response_text="Routing Decision", model="llama-3.3-70b-versatile")

        def mock_loader(name, model=None):
            if name == "groq":
                return mock_groq
            return None

        router.get_concrete_provider = mock_loader

        response = run_coro(router.chat("Route this query", task_type="routing"))
        self.assertEqual(response, "Routing Decision")
        meta = router.last_execution_meta
        self.assertEqual(meta["tier_used"], "fast")
        self.assertEqual(meta["task_type"], "routing")
        self.assertEqual(meta["provider_used"], "groq")

    def test_router_chat_sync_tier(self):
        """Test chat_sync() bridges synchronously with tier selection."""
        router = ResilientLLMProvider()
        mock_groq = MockLLM(response_text="Fast Sync Answer", model="llama-3.3-70b-versatile")

        router.get_concrete_provider = lambda name, model=None: mock_groq if name == "groq" else None

        result = router.chat_sync("Hello fast tier", tier="fast")
        self.assertEqual(result, "Fast Sync Answer")
        self.assertEqual(router.last_execution_meta["tier_used"], "fast")


class TestSupervisorTierSpecialization(unittest.TestCase):
    """Tests for Supervisor tier specialization wiring."""

    def test_supervisor_agent_tiers(self):
        """Verify Supervisor instantiates agents with tier-specialized LLMs."""
        supervisor = Supervisor(use_tier_routing=True)
        # Supervisor router LLM should be FAST tier
        self.assertIsInstance(supervisor.llm, ResilientLLMProvider)
        self.assertEqual(supervisor.llm.get_config()["active_tier"], "fast")

        # Coding agent should be COMPLEX tier
        coding_llm = supervisor.coding_agent.llm
        self.assertIsInstance(coding_llm, ResilientLLMProvider)
        self.assertEqual(coding_llm.get_config()["active_tier"], "complex")

        # Review agent should be BALANCED tier
        review_llm = supervisor.review_agent.llm
        self.assertIsInstance(review_llm, ResilientLLMProvider)
        self.assertEqual(review_llm.get_config()["active_tier"], "balanced")

        # Testing agent should be BALANCED tier
        testing_llm = supervisor.testing_agent.llm
        self.assertIsInstance(testing_llm, ResilientLLMProvider)
        self.assertEqual(testing_llm.get_config()["active_tier"], "balanced")

    def test_supervisor_explicit_override_backward_compatibility(self):
        """Verify passing explicit llm_provider overrides tier routing for all agents."""
        mock_llm = MockLLM(response_text="Custom Override")
        supervisor = Supervisor(llm_provider=mock_llm)
        self.assertEqual(supervisor.llm, mock_llm)
        self.assertEqual(supervisor.coding_agent.llm, mock_llm)
        self.assertEqual(supervisor.review_agent.llm, mock_llm)
        self.assertEqual(supervisor.testing_agent.llm, mock_llm)

    def test_supervisor_classify_intent_llm_fallback(self):
        """Verify classify_intent_llm falls back gracefully if LLM returns non-JSON."""
        mock_llm = MockLLM(response_text="I am not returning json")
        supervisor = Supervisor(llm_provider=mock_llm)
        res = supervisor.classify_intent_llm("Fix the login bug in auth.py")
        self.assertEqual(res["intent"], "CODING")
        self.assertEqual(res["pipeline"], ["coding"])


class TestAgentBuilderTierSpecialization(unittest.TestCase):
    """Tests for AgentSpec and AgentBuilder model_tier support."""

    def test_agent_spec_model_tier_validation(self):
        """Verify valid tiers are accepted and invalid tiers are rejected."""
        spec = AgentSpec(
            name="test_fast_agent",
            role="Speedy Helper",
            system_instruction="Assist quickly with queries.",
            model_tier="fast",
        )
        self.assertEqual(spec.model_tier, "fast")
        self.assertEqual(spec.model_dump()["model_tier"], "fast")

        # Invalid tier raises ValueError
        with self.assertRaises(ValueError):
            AgentSpec(
                name="invalid_tier_agent",
                role="Broken Helper",
                system_instruction="Should fail on invalid tier.",
                model_tier="super_galaxy_tier",
            )

    def test_starter_templates_have_specialized_tiers(self):
        """Verify starter blueprints define tailored model tiers."""
        self.assertEqual(STARTER_TEMPLATES["documentation_agent"].model_tier, "balanced")
        self.assertEqual(STARTER_TEMPLATES["security_auditor"].model_tier, "complex")
        self.assertEqual(STARTER_TEMPLATES["refactoring_agent"].model_tier, "complex")
        self.assertEqual(STARTER_TEMPLATES["devops_agent"].model_tier, "fast")

    def test_agent_builder_resolves_tier_llm(self):
        """Verify AgentBuilder assigns tier-specialized LLM to built agents."""
        builder = AgentBuilder()
        agent = builder.build_agent(
            {
                "name": "auto_tiered_agent",
                "role": "Complex Analyst",
                "system_instruction": "Perform deep architectural analysis.",
                "model_tier": "complex",
            },
            save=False,
        )
        self.assertIsInstance(agent.llm, ResilientLLMProvider)
        self.assertEqual(agent.llm.get_config()["active_tier"], "complex")


class TestFastAPITierEndpoints(unittest.TestCase):
    """Tests for Phase 22 FastAPI tier endpoints."""

    def test_get_tiers_route(self):
        """Verify GET /llm/tiers returns full tier list and mappings."""
        from backend.routers.llm import get_model_tiers

        res = run_coro(get_model_tiers())
        self.assertIn("tiers", res)
        self.assertIn("task_mappings", res)
        tier_names = [t["tier"] for t in res["tiers"]]
        self.assertIn("fast", tier_names)
        self.assertIn("complex", tier_names)
        self.assertEqual(res["task_mappings"]["coding"], "complex")

    def test_configure_tier_route(self):
        """Verify POST /llm/tiers/configure updates registry."""
        from backend.routers.llm import configure_model_tier, ConfigureTierRequest

        req = ConfigureTierRequest(
            tier="fast",
            model_name="llama-3.1-8b-instant",
            temperature=0.1,
        )
        res = run_coro(configure_model_tier(req))
        self.assertEqual(res["status"], "updated")
        self.assertEqual(res["tier"]["model_name"], "llama-3.1-8b-instant")
        self.assertEqual(res["tier"]["temperature"], 0.1)

    def test_route_tier_chat_endpoint(self):
        """Verify POST /llm/tiers/route executes with mock router."""
        from backend.routers.llm import route_tier_chat, TierChatRequest, default_llm_router

        mock_provider = MockLLM(response_text="API Tier Response", model="gemini-2.5-pro")
        default_llm_router.get_concrete_provider = lambda name, model=None: mock_provider

        req = TierChatRequest(
            message="Test prompt",
            tier="complex",
        )
        res = run_coro(route_tier_chat(req))
        self.assertEqual(res.response, "API Tier Response")
        self.assertEqual(res.tier, "complex")


if __name__ == "__main__":
    unittest.main()

