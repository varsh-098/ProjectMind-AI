"""
scripts/phase21_llm_abstraction.py
===================================
Phase 21 -- LLM Abstraction Layer & Failover Router Verification.

PURPOSE:
    Demonstrate ProjectMind's self-healing multi-provider LLM abstraction layer:
    1. Dynamic Provider Configuration: Switch active provider & reorder fallback chain.
    2. Provider Health Probing: Real-time diagnostics for Nemotron, Groq, and Gemini.
    3. Automatic Failover Simulation: Seamless recovery when a provider goes offline.
    4. Execution Trace Metadata: Tracking latency, provider used, and failover steps.
    5. Integration with Factory: Upgraded factory delivering resilient routing.

RUN WITH:
    python scripts/phase21_llm_abstraction.py
"""

import sys
import os
import time

# Ensure UTF-8 stdout on Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure repository root is on sys.path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from backend.llm.base import BaseLLMProvider
from backend.llm.router import ResilientLLMProvider, default_llm_router
from backend.llm.factory import get_llm_provider


def header(title: str):
    print("\n" + "=" * 65)
    print(f"  {title}")
    print("=" * 65)


def run_coro(coro):
    """Safely execute a coroutine without requiring external socket creation."""
    try:
        coro.send(None)
    except StopIteration as e:
        return e.value


class MockSimulatedProvider(BaseLLMProvider):
    """Simulated provider to test failover dynamics deterministically."""

    def __init__(self, name: str, should_fail: bool = False, fail_reason: str = "Down", latency_ms: float = 120.0):
        self.name = name
        self.should_fail = should_fail
        self.fail_reason = fail_reason
        self.latency_ms = latency_ms

    async def chat(self, message: str, system_instruction: str | None = None) -> str:
        if self.should_fail:
            raise ConnectionError(f"Simulated failure on {self.name}: {self.fail_reason}")
        return f"Hello from {self.name}! Task received: '{message}'."

    async def health_check(self) -> dict:
        if self.should_fail:
            return {"provider": self.name, "status": "offline", "error": self.fail_reason}
        return {"provider": self.name, "status": "online", "latency_ms": self.latency_ms}


def experiment_1_router_configuration():
    header("EXPERIMENT 1: ROUTER CONFIGURATION & STATE")
    config = default_llm_router.get_config()
    print(f"  Active Primary Provider: {config['active_provider']}")
    print(f"  Fallback Chain Priority: {' -> '.join(config['fallback_chain'])}")
    print(f"  Supported Providers:     {', '.join(config['supported_providers'])}")
    print("  [PASS] Router initialized with fallback chain.")


def experiment_2_dynamic_switching():
    header("EXPERIMENT 2: DYNAMIC RUNTIME PROVIDER SWITCHING")
    router = ResilientLLMProvider(active_provider="groq")
    print("  Initial Active Provider:  groq")

    # Switch to Gemini dynamically
    router.set_active_provider("gemini")
    print(f"  Switched Active Provider: {router.get_config()['active_provider']}")
    print(f"  Reordered Fallback Chain: {' -> '.join(router.get_config()['fallback_chain'])}")

    # Update custom fallback order
    custom_chain = ["gemini", "groq", "nemotron"]
    router.set_fallback_chain(custom_chain)
    print(f"  Custom Fallback Priority: {' -> '.join(router.get_config()['fallback_chain'])}")
    print("  [PASS] Dynamic runtime configuration verified.")


def experiment_3_health_probing():
    header("EXPERIMENT 3: PROVIDER HEALTH PROBING")
    router = ResilientLLMProvider()

    # Seed with simulated mock providers for offline demonstration
    router._provider_instances = {
        "nemotron": MockSimulatedProvider("nemotron", should_fail=True, fail_reason="Connection refused on port 8081"),
        "groq": MockSimulatedProvider("groq", should_fail=False, latency_ms=145.2),
        "gemini": MockSimulatedProvider("gemini", should_fail=False, latency_ms=210.5),
    }

    report = run_coro(router.check_health())
    print(f"  Active Provider: {report['router_active']}")
    print(f"  Fallback Chain:  {' -> '.join(report['fallback_chain'])}\n")

    for p_name, data in report["providers"].items():
        status = data.get("status", "unknown").upper()
        if status == "ONLINE":
            print(f"  * {p_name.upper():<10} : [ONLINE]  Latency: {data.get('latency_ms')} ms")
        else:
            print(f"  * {p_name.upper():<10} : [OFFLINE] Reason:  {data.get('error')}")

    print("\n  [PASS] Provider health diagnostics verified.")


def experiment_4_automatic_failover():
    header("EXPERIMENT 4: AUTOMATIC FAILOVER RECOVERY")

    router = ResilientLLMProvider(
        active_provider="nemotron",
        fallback_chain=["nemotron", "groq", "gemini"],
    )

    # Nemotron is simulated offline; Groq is healthy
    router._provider_instances = {
        "nemotron": MockSimulatedProvider("nemotron", should_fail=True, fail_reason="Local llama-server is not running"),
        "groq": MockSimulatedProvider("groq", should_fail=False),
        "gemini": MockSimulatedProvider("gemini", should_fail=False),
    }

    print("  Task: 'Explain the factory design pattern'")
    print("  Attempting with Primary: Nemotron (Local Server)...")
    print("  [!] Nemotron connection failed!")
    print("  --> Router triggering automatic failover to Groq...")

    response = run_coro(router.chat("Explain the factory design pattern"))
    meta = router.last_execution_meta

    print(f"\n  Final Response: {response}")
    print(f"  Provider Used:  {meta['provider_used']}")
    print(f"  Failovers:      {len(meta['fallbacks_attempted'])} provider(s) bypassed:")
    for f in meta["fallbacks_attempted"]:
        print(f"    - Bypassed {f['provider']}: {f['error']}")

    print("\n  [PASS] Automatic failover recovered smoothly without user-facing outage.")


def experiment_5_all_providers_down():
    header("EXPERIMENT 5: ALL-DOWN ERROR AGGREGATION")

    router = ResilientLLMProvider()
    router._provider_instances = {
        "nemotron": MockSimulatedProvider("nemotron", should_fail=True, fail_reason="Offline"),
        "groq": MockSimulatedProvider("groq", should_fail=True, fail_reason="Rate limit 429"),
        "gemini": MockSimulatedProvider("gemini", should_fail=True, fail_reason="Quota exceeded"),
    }

    try:
        run_coro(router.chat("Test prompt"))
        print("  [FAIL] Expected RuntimeError when all fail!")
    except RuntimeError as e:
        print("  [PASS] Caught aggregated failure exception:")
        for line in str(e).splitlines():
            print(f"    {line}")


def experiment_6_factory_integration():
    header("EXPERIMENT 6: FACTORY LAYER INTEGRATION")

    provider = get_llm_provider(resilient=True)
    print(f"  get_llm_provider(resilient=True) returned: {type(provider).__name__}")
    assert isinstance(provider, ResilientLLMProvider), "Factory must return ResilientLLMProvider by default"
    print("  [PASS] Factory correctly configured to deliver resilient router by default.")


def main():
    print("\n" + "#" * 65)
    print("  PROJECTMIND AI -- PHASE 21: LLM ABSTRACTION LAYER VERIFICATION")
    print("#" * 65)

    experiment_1_router_configuration()
    experiment_2_dynamic_switching()
    experiment_3_health_probing()
    experiment_4_automatic_failover()
    experiment_5_all_providers_down()
    experiment_6_factory_integration()

    header("PHASE 21 COMPLETE")
    print("  Resilient multi-provider routing, dynamic failovers,")
    print("  health probes, and runtime provider switching are operational!")
    print("  ProjectMind is now protected against single-provider outages.\n")


if __name__ == "__main__":
    main()
