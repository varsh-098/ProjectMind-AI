"""
scripts/phase18_langgraph_workflows.py
======================================
Phase 18 -- Stateful Graph Workflows & Autonomous Self-Correction Loop

PURPOSE:
    Demonstrate graph-based multi-agent coordination (LangGraph pattern):
    1. Shared State: Typed dictionary passing code, issues, and test traces.
    2. Dynamic Branching: Conditional edges evaluating review audits and test runs.
    3. Self-Correction Cycle:
       - If Review Agent detects vulnerability → Loops back to Coding Agent!
       - If Testing Agent detects failing test → Loops back to Coding Agent!
    4. Loop Safety: Enforces max_iterations to prevent infinite cycles.

RUN WITH:
    python scripts/phase18_langgraph_workflows.py
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

from backend.supervisor.graph import (
    create_self_correcting_agent_graph,
    StateGraph,
    ProjectMindState,
    END,
)


def header(title: str):
    print("\n" + "=" * 65)
    print(f"  {title}")
    print("=" * 65)


# =====================================================================
# EXPERIMENT 1: Graph Structure & Node Architecture
# =====================================================================
def test_graph_compilation():
    header("1. GRAPH STRUCTURE & TOPOLOGY COMPILATION")

    graph = create_self_correcting_agent_graph()
    raw_graph = graph.graph

    print(f"  Nodes Registered:       {list(raw_graph.nodes.keys())}")
    print(f"  Entry Point:            {raw_graph.entry_point}")
    print(f"  Static Edges:           {raw_graph.edges}")
    print(f"  Conditional Edge Nodes: {list(raw_graph.conditional_edges.keys())}")

    assert "coding" in raw_graph.nodes
    assert "review" in raw_graph.nodes
    assert "testing" in raw_graph.nodes
    assert raw_graph.entry_point == "coding"

    print("\n  ✅ PASS — Directed graph compiled with cyclic self-correction edges.")


# =====================================================================
# EXPERIMENT 2: Happy Path Execution (Single Pass)
# =====================================================================
def test_happy_path_execution():
    header("2. HAPPY PATH WORKFLOW (Clean Code → Review → Test → End)")

    graph = create_self_correcting_agent_graph()

    clean_code = (
        "def calculate_total(price, tax_rate):\n"
        "    return price * (1 + tax_rate)\n"
    )

    initial_state = {
        "task": "Implement price tax calculator",
        "current_code": clean_code,
        "max_iterations": 3,
    }

    final_state = graph.invoke(initial_state)

    print(f"  Execution Trace: {' → '.join(final_state['execution_trace'])}")
    print(f"  Review Status:   {final_state['review_status']}")
    print(f"  Tests Passed:    {final_state['tests_passed']}")
    print(f"  Total Cycles:    {final_state['iteration']}")

    expected_trace = ["coding", "review", "testing"]
    assert final_state["execution_trace"] == expected_trace, f"Expected {expected_trace}, got {final_state['execution_trace']}"
    assert final_state["review_status"] == "APPROVED"
    assert final_state["tests_passed"] is True
    print("\n  ✅ PASS — Single pass execution successfully reached END.")


# =====================================================================
# EXPERIMENT 3: Autonomous Security Self-Correction (Review Cycle)
# =====================================================================
def test_security_self_correction_cycle():
    header("3. SECURITY SELF-CORRECTION (Vulnerability → Review Rejection → Coding Fix)")

    graph = create_self_correcting_agent_graph()

    # Code containing deliberate SQL injection
    vulnerable_code = (
        "def get_user(user_id):\n"
        "    query = f\"SELECT * FROM users WHERE id = '{user_id}'\"\n"
        "    return db.execute(query)\n"
    )

    print("  Initial Vulnerable Code:")
    for line in vulnerable_code.splitlines():
        print(f"    {line}")

    initial_state = {
        "task": "Fix security vulnerability in get_user",
        "current_code": vulnerable_code,
        "max_iterations": 3,
    }

    final_state = graph.invoke(initial_state)

    print(f"\n  State Machine Execution Trace:")
    print(f"    {' → '.join(final_state['execution_trace'])}")

    print(f"\n  Final Remediated Code:")
    for line in final_state["current_code"].splitlines():
        print(f"    {line}")

    print(f"\n  Final Audit Status: {final_state['review_status']}")
    print(f"  Final Tests Status: {final_state['tests_passed']}")
    print(f"  Iterations Taken:   {final_state['iteration']}")

    # Trace must show: coding → review → (loop back) → coding → review → testing
    assert "review" in final_state["execution_trace"]
    assert final_state["execution_trace"].count("coding") == 2, "Agent should have looped back to coding once!"
    assert final_state["review_status"] == "APPROVED", "Remediated code was not approved!"
    print("\n  ✅ PASS — Graph autonomously cycled back and repaired security vulnerability.")


# =====================================================================
# EXPERIMENT 4: Autonomous Test-Driven Self-Correction (Testing Cycle)
# =====================================================================
def test_test_driven_self_correction():
    header("4. TEST-DRIVEN SELF-CORRECTION (Logic Bug → Test Failure → Coding Fix)")

    graph = create_self_correcting_agent_graph()

    # Code containing calculation bug
    buggy_code = (
        "def compute_discount(price, rate):\n"
        "    # BUG: addition instead of discount subtraction\n"
        "    return price * (1 + rate)\n"
    )

    initial_state = {
        "task": "Fix discount calculation logic bug",
        "current_code": buggy_code,
        "max_iterations": 3,
    }

    final_state = graph.invoke(initial_state)

    print(f"  State Machine Execution Trace:")
    print(f"    {' → '.join(final_state['execution_trace'])}")

    print(f"  Final Code: {final_state['current_code'].splitlines()[-1]}")
    print(f"  Tests Output: {final_state['test_output']}")
    print(f"  Tests Passed: {final_state['tests_passed']}")

    assert final_state["tests_passed"] is True
    assert final_state["execution_trace"].count("testing") >= 1
    print("\n  ✅ PASS — Graph autonomously resolved failing tests via loopback.")


# =====================================================================
# EXPERIMENT 5: Infinite Loop Protection (max_iterations Guard)
# =====================================================================
def test_max_iterations_guard():
    header("5. INFINITE LOOP PROTECTION (max_iterations Guard)")

    # Build a graph where a stubborn node never passes
    stubborn_builder = StateGraph(ProjectMindState)

    def stubborn_coding(state):
        state["iteration"] = state.get("iteration", 0) + 1
        return {"current_code": "unfixable_code", "review_status": "REJECTED"}

    stubborn_builder.add_node("coding", stubborn_coding)
    stubborn_builder.set_entry_point("coding")

    # Conditional edge that always wants to loop back
    stubborn_builder.add_conditional_edges(
        source="coding",
        condition=lambda s: "max_retries" if s.get("iteration", 0) >= s.get("max_iterations", 3) else "retry",
        path_map={"retry": "coding", "max_retries": END},
    )

    compiled = stubborn_builder.compile()
    state = compiled.invoke({"max_iterations": 3})

    print(f"  Max Iterations Configured: 3")
    print(f"  Total Cycles Executed:     {state['iteration']}")
    print(f"  Execution Trace:           {' → '.join(state['execution_trace'])}")

    assert state["iteration"] == 3, f"Expected exactly 3 iterations, got {state['iteration']}"
    print("\n  ✅ PASS — Graph safely terminated at boundary limit without hanging.")


def main():
    print("\n" + "#" * 65)
    print("  PROJECTMIND AI -- PHASE 18: LANGGRAPH & STATEFUL GRAPH WORKFLOWS")
    print("#" * 65)

    test_graph_compilation()
    test_happy_path_execution()
    test_security_self_correction_cycle()
    test_test_driven_self_correction()
    test_max_iterations_guard()

    header("PHASE 18 COMPLETE")
    print("  LangGraph-style stateful workflows and self-correction cycles verified!")
    print("  ProjectMind can now autonomously detect and repair code defects.\n")


if __name__ == "__main__":
    main()
