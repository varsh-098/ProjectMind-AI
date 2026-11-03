"""
backend/llm/model_registry.py
==============================
Phase 22 — Multiple Model Support & Task-to-Model Specialization.

PURPOSE:
    Routes tasks to the most suitable LLM based on latency, cost, and reasoning depth:
      - FAST: Ultra low-latency (<300ms) for supervisor routing, classification, tool dispatching.
      - BALANCED: Balanced reasoning & speed for code review, test generation, documentation.
      - COMPLEX: High-capacity reasoning for code generation, architectural decisions, refactoring.
      - LOCAL: Air-gapped / offline privacy for sensitive codebase inspection on local llama-server.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
import copy

from backend.config import settings
from backend.llm.base import BaseLLMProvider


class ModelTier(str, Enum):
    """Execution tiers for task-to-model specialization."""
    FAST = "fast"
    BALANCED = "balanced"
    COMPLEX = "complex"
    LOCAL = "local"


@dataclass
class ModelProfile:
    """Configuration profile for a specific model tier."""
    tier: str
    provider: str
    model_name: str
    description: str = ""
    fallback_chain: List[str] = field(default_factory=list)
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to serializable dictionary."""
        return {
            "tier": self.tier,
            "provider": self.provider,
            "model_name": self.model_name,
            "description": self.description,
            "fallback_chain": list(self.fallback_chain),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "metadata": dict(self.metadata),
        }


# Default task type to tier mappings
DEFAULT_TASK_MAPPINGS: Dict[str, str] = {
    # Fast tier (<300ms)
    "routing": ModelTier.FAST.value,
    "classification": ModelTier.FAST.value,
    "intent": ModelTier.FAST.value,
    "memory": ModelTier.FAST.value,
    "summary": ModelTier.FAST.value,
    "quick_chat": ModelTier.FAST.value,

    # Balanced tier (Speed + Precision)
    "review": ModelTier.BALANCED.value,
    "testing": ModelTier.BALANCED.value,
    "documentation": ModelTier.BALANCED.value,
    "devops": ModelTier.BALANCED.value,
    "general": ModelTier.BALANCED.value,

    # Complex tier (Deep Reasoning & Generation)
    "coding": ModelTier.COMPLEX.value,
    "refactoring": ModelTier.COMPLEX.value,
    "architecture": ModelTier.COMPLEX.value,
    "security": ModelTier.COMPLEX.value,
    "reasoning": ModelTier.COMPLEX.value,

    # Local tier (Privacy-first / Air-gapped)
    "local": ModelTier.LOCAL.value,
    "offline": ModelTier.LOCAL.value,
    "private": ModelTier.LOCAL.value,
}


class ModelRegistry:
    """
    Central registry managing model tiers, task mappings, and tier-specific
    provider instantiation.
    """

    def __init__(self):
        self._profiles: Dict[str, ModelProfile] = {}
        self._task_mappings: Dict[str, str] = dict(DEFAULT_TASK_MAPPINGS)
        self.reset_to_defaults()

    def reset_to_defaults(self) -> None:
        """Reset all tiers and task mappings to configuration defaults."""
        self._task_mappings = dict(DEFAULT_TASK_MAPPINGS)
        self._profiles = {
            ModelTier.FAST.value: ModelProfile(
                tier=ModelTier.FAST.value,
                provider=getattr(settings, "tier_fast_provider", "groq"),
                model_name=getattr(settings, "tier_fast_model", "llama-3.3-70b-versatile"),
                description="Ultra low-latency for routing, classification, and quick lookups.",
                fallback_chain=["groq", "nemotron", "gemini"],
                temperature=0.3,
            ),
            ModelTier.BALANCED.value: ModelProfile(
                tier=ModelTier.BALANCED.value,
                provider=getattr(settings, "tier_balanced_provider", "gemini"),
                model_name=getattr(settings, "tier_balanced_model", "gemini-2.5-flash"),
                description="Balanced latency and precision for review, testing, and docs.",
                fallback_chain=["gemini", "groq", "nemotron"],
                temperature=0.5,
            ),
            ModelTier.COMPLEX.value: ModelProfile(
                tier=ModelTier.COMPLEX.value,
                provider=getattr(settings, "tier_complex_provider", "gemini"),
                model_name=getattr(settings, "tier_complex_model", "gemini-2.5-pro"),
                description="Deep reasoning for code generation and multi-step refactoring.",
                fallback_chain=["gemini", "groq", "nemotron"],
                temperature=0.7,
            ),
            ModelTier.LOCAL.value: ModelProfile(
                tier=ModelTier.LOCAL.value,
                provider=getattr(settings, "tier_local_provider", "nemotron"),
                model_name=getattr(settings, "tier_local_model", "nemotron"),
                description="Air-gapped privacy on local llama-server with zero cloud egress.",
                fallback_chain=["nemotron"],
                temperature=0.7,
            ),
        }

    # ------------------------------------------------------------------
    # Profile & Tier Management
    # ------------------------------------------------------------------

    def get_profile(self, tier: str | ModelTier) -> Optional[ModelProfile]:
        """Retrieve profile by tier name or enum."""
        key = (tier.value if isinstance(tier, ModelTier) else str(tier)).strip().lower()
        profile = self._profiles.get(key)
        if profile:
            # Return a copy to prevent accidental mutation of internal state
            return copy.deepcopy(profile)
        return None

    def register_profile(self, tier: str | ModelTier, profile: ModelProfile) -> None:
        """Register or overwrite a model profile for a tier."""
        key = (tier.value if isinstance(tier, ModelTier) else str(tier)).strip().lower()
        if not key:
            raise ValueError("Tier name cannot be empty.")
        self._profiles[key] = copy.deepcopy(profile)

    def update_profile(
        self,
        tier: str | ModelTier,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        description: Optional[str] = None,
        fallback_chain: Optional[List[str]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> ModelProfile:
        """Update fields of an existing tier profile."""
        key = (tier.value if isinstance(tier, ModelTier) else str(tier)).strip().lower()
        if key not in self._profiles:
            raise KeyError(f"Tier '{tier}' not found in registry.")

        prof = self._profiles[key]
        if provider is not None:
            prof.provider = provider.strip().lower()
        if model_name is not None:
            prof.model_name = model_name.strip()
        if description is not None:
            prof.description = description
        if fallback_chain is not None:
            prof.fallback_chain = [p.strip().lower() for p in fallback_chain]
        if temperature is not None:
            prof.temperature = temperature
        if max_tokens is not None:
            prof.max_tokens = max_tokens
        if kwargs:
            prof.metadata.update(kwargs)

        return copy.deepcopy(prof)

    def list_tiers(self) -> List[Dict[str, Any]]:
        """Return list of all registered tier configurations."""
        return [p.to_dict() for p in self._profiles.values()]

    # ------------------------------------------------------------------
    # Task-to-Tier Mapping
    # ------------------------------------------------------------------

    def get_tier_for_task(self, task_type: str) -> str:
        """Resolve a task name to its configured model tier."""
        clean = (task_type or "").strip().lower()
        if clean in self._profiles:
            return clean
        return self._task_mappings.get(clean, ModelTier.BALANCED.value)

    def map_task(self, task_type: str, tier: str | ModelTier) -> None:
        """Map a task identifier to a specific model tier."""
        task_clean = task_type.strip().lower()
        tier_clean = (tier.value if isinstance(tier, ModelTier) else str(tier)).strip().lower()
        if tier_clean not in self._profiles:
            raise ValueError(
                f"Unknown tier '{tier_clean}'. Available tiers: {list(self._profiles.keys())}"
            )
        self._task_mappings[task_clean] = tier_clean

    def list_task_mappings(self) -> Dict[str, str]:
        """Return all current task-to-tier mappings."""
        return dict(self._task_mappings)

    # ------------------------------------------------------------------
    # Provider Resolution
    # ------------------------------------------------------------------

    def get_provider_for_tier(
        self,
        tier: str | ModelTier,
        resilient: bool = True,
    ) -> BaseLLMProvider:
        """
        Instantiate an LLM provider specialized for the given tier.

        Args:
            tier: Target tier (FAST, BALANCED, COMPLEX, LOCAL).
            resilient: If True, returns ResilientLLMProvider with failover chain
                       tuned to this tier's primary provider and model.
        """
        key = (tier.value if isinstance(tier, ModelTier) else str(tier)).strip().lower()
        profile = self._profiles.get(key)
        if not profile:
            raise KeyError(
                f"Unknown model tier: '{key}'. Available tiers: {list(self._profiles.keys())}"
            )

        if resilient:
            from backend.llm.router import ResilientLLMProvider
            model_overrides = {profile.provider: profile.model_name}
            chain = [profile.provider]
            for p in profile.fallback_chain:
                if p not in chain:
                    chain.append(p)

            return ResilientLLMProvider(
                active_provider=profile.provider,
                fallback_chain=chain,
                model_overrides=model_overrides,
                active_tier=key,
            )

        # Concrete non-resilient provider
        p_name = profile.provider
        if p_name == "groq":
            from backend.llm.groq_provider import GroqProvider
            return GroqProvider(model=profile.model_name)
        elif p_name == "gemini":
            from backend.llm.gemini_provider import GeminiProvider
            return GeminiProvider(model=profile.model_name)
        elif p_name == "nemotron":
            from backend.llm.nemotron import NemotronProvider
            return NemotronProvider(model=profile.model_name)
        else:
            raise ValueError(f"Unsupported provider '{p_name}' in tier '{key}'.")

    def get_provider_for_task(
        self,
        task_type: str,
        resilient: bool = True,
    ) -> BaseLLMProvider:
        """
        Instantiate an LLM provider specialized for the given task type.
        """
        tier = self.get_tier_for_task(task_type)
        return self.get_provider_for_tier(tier, resilient=resilient)


# Global singleton instance
model_registry = ModelRegistry()

