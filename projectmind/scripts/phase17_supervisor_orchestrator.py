"""
scripts/phase17_supervisor_orchestrator.py
==========================================
Phase 17 -- Supervisor Orchestration & Dynamic Routing Verification

PURPOSE:
    Demonstrate that the Supervisor dynamically routes developer requests:
    1. Intent Classification: Determines whether a task needs Memory, a single agent,
       or a multi-agent collaborative pipeline.
    2. Zero-Overhead Fast-Path: Factual questions route directly to Memory.
    3. Single-Agent Routing: Review or Testing tasks invoke only their respective agent.
    4. Multi-Agent Pipeline: Chained execution (e.g. Coding → Testing → Review)
       with state and context passing between stages.

RUN WITH:
    python scripts/phase17_supervisor_orchestrator.py
"""

import sys
import os
import json

# Set stdout encoding for Windows console
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure repository root is on sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
projectmind_dir = os.path.dirname(script_dir)
workspace_root = os.path.dirname(projectmind_dir)

for p in (workspace_root, projectmind_dir):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.supervisor.supervisor import Supervisor


def header(title: str):
    print("\n" + "=" * 65)
    print(f"  {title}")
    print("=" * 65)


# =====================================================================
# EXPERIMENT 1: Intent Classification & Dynamic Routing Matrix
# =====================================================================
def test_dynamic_routing_matrix():
    header("1. DYNAMIC ROUTING INTENT CLASSIFICATION")

    supervisor = Supervisor()

    test_queries = [
        ("What database and tech stack does ProjectMind use?", "MEMORY", ["memory"]),
        ("Review my authentication controller for SQL injection", "REVIEW", ["review"]),
        ("Run the project unit test suite", "TESTING", ["testing"]),
        ("Fix the discount calculation bug and run tests to verify", "PIPELINE", ["coding", "testing"]),
        ("Write a new payment module, review for security, and run tests", "PIPELINE", ["coding", "review", "testing"]),
    ]

    print(f"  {'User Query':<50} | {'Intent':<10} | {'Pipeline'}")
    print("  " + "-" * 75)

    for query, expected_intent, expected_pipeline in test_queries:
        plan = supervisor.classify_intent(query)
        print(f"  • {query[:48]:<48}... | {plan['intent']:<10} | {' → '.join(plan['pipeline'])}")

        assert plan["intent"] == expected_intent, f"Wrong intent for '{query}': got {plan['intent']}"
        assert plan["pipeline"] == expected_pipeline, f"Wrong pipeline for '{query}': got {plan['pipeline']}"

    print("\n  ✅ PASS — All 5 query patterns routed to optimal agents/pipelines.")


# =====================================================================
# EXPERIMENT 2: Zero-Overhead Direct Memory Fast-Path
# =====================================================================
def test_memory_fast_path():
    header("2. DIRECT MEMORY FAST-PATH (Zero LLM Token Overhead)")

    supervisor = Supervisor()
    query = "What database and LLM providers are supported?"

    print(f"  Dispatching Query: \"{query}\"")
    result = supervisor.execute(query)

    print(f"    Intent:          {result['intent']}")
    print(f"    Stages Executed: {result['stages_executed']}")
    print(f"    Summary:         {result['summary']}")

    memory_matches = result["results"]["memory"]["matches"]
    print(f"\n    Retrieved Memory Matches ({len(memory_matches)}):")
    for m in memory_matches[:2]:
        tag = m.get("category") or m.get("type", "memory")
        title = m.get("key") or m.get("title", "item")
        print(f"      • [{tag}] {title}: {m.get('content', '')[:70]}...")

    assert result["intent"] == "MEMORY"
    assert len(memory_matches) > 0
    print("\n  ✅ PASS — Architectural knowledge served in 0 agent loop iterations.")


# =====================================================================
# EXPERIMENT 3: Single-Agent Dynamic Dispatch
# =====================================================================
def test_single_agent_dispatch():
    header("3. SINGLE-AGENT DYNAMIC ROUTING")

    supervisor = Supervisor()
    query = "Audit the security of database queries in backend/brain/tools.py"

    print(f"  Dispatching Query: \"{query}\"")
    result = supervisor.execute(query)

    print(f"    Intent:          {result['intent']}")
    print(f"    Stages Executed: {result['stages_executed']}")
    print(f"    Agent Activated: {list(result['results'].keys())}")

    # Verify ONLY the Review Agent was activated (no Coding or Testing overhead)
    assert result["stages_executed"] == ["review"]
    assert "coding" not in result["results"]
    assert "testing" not in result["results"]
    print("\n  ✅ PASS — Only the requested specialist was mobilized.")


# =====================================================================
# EXPERIMENT 4: Multi-Agent Sequential Pipeline Orchestration
# =====================================================================
def test_multi_agent_pipeline_execution():
    header("4. MULTI-AGENT SEQUENTIAL PIPELINE (Coding → Testing)")

    supervisor = Supervisor()
    query = "Fix the login bug and run tests to verify"

    print(f"  Dispatching Multi-Step Task: \"{query}\"")
    result = supervisor.execute(query)

    print(f"    Pipeline Plan:   {' → '.join(result['stages_executed'])}")
    print(f"    Stage 1 Result:  {result['results']['coding']['agent']} completed {result['results']['coding']['turns_executed']} turn(s).")
    print(f"    Stage 2 Result:  {result['results']['testing']['agent']} completed {result['results']['testing']['turns_executed']} turn(s).")
    print(f"    Executive Summary: {result['summary']}")

    assert result["stages_executed"] == ["coding", "testing"]
    assert "coding" in result["results"]
    assert "testing" in result["results"]
    print("\n  ✅ PASS — Chained multi-agent collaboration executed successfully.")


def main():
    print("\n" + "#" * 65)
    print("  PROJECTMIND AI -- PHASE 17: SUPERVISOR ORCHESTRATOR")
    print("#" * 65)

    test_dynamic_routing_matrix()
    test_memory_fast_path()
    test_single_agent_dispatch()
    test_multi_agent_pipeline_execution()

    header("PHASE 17 COMPLETE")
    print("  Supervisor dynamic routing & multi-agent pipelines fully verified!")
    print("  ProjectMind now operates as a complete multi-agent system.\n")


if __name__ == "__main__":
    main()
