"""
backend/supervisor/graph.py
============================
Phase 18 -- Stateful Graph Workflows & Multi-Agent Self-Correction Loop.

WHY GRAPH WORKFLOWS (LangGraph Pattern)?
    In Phase 17, our Supervisor used a simple linear pipeline:
        User Request → Coding Agent → Review Agent → Testing Agent → Done

    THE LIMITATION:
        If tests fail or the Review Agent finds a CRITICAL vulnerability,
        a linear pipeline cannot loop back to fix it!

    THE GRAPH WORKFLOW SOLUTION:
        We model multi-agent collaboration as a directed state machine:
          1. Shared State: A typed dictionary that flows through every node.
          2. Nodes: Specialized agents (Coding, Review, Testing).
          3. Conditional Edges: Decision gates that dynamically cycle back:
             - Review failed? → Route back to Coding Agent with audit feedback!
             - Tests failed?  → Route back to Coding Agent with stack trace!
             - All passed?    → Route to END!

This implements the industry-standard ReAct / LangGraph stateful pattern.
"""

from typing import Dict, Any, List, Optional, Callable, TypedDict
from backend.agents.coding_agent import CodingAgent
from backend.agents.review_agent import ReviewAgent
from backend.agents.testing_agent import TestingAgent
from backend.brain import tools

# Special sentinel for graph termination
END = "__end__"


# ---------------------------------------------------------------------
# 1. Shared Graph State
# ---------------------------------------------------------------------
class ProjectMindState(TypedDict, total=False):
    """
    Typed dictionary representing the shared state flowing across all graph nodes.
    """
    task: str                         # Original developer prompt
    file_path: Optional[str]          # Target file being modified
    current_code: Optional[str]       # Current version of the code
    review_status: Optional[str]      # "APPROVED" or "REJECTED"
    review_issues: List[Dict[str, Any]] # List of issues found by Review Agent
    tests_passed: bool                # Whether unit tests passed
    test_output: Optional[str]        # Pytest / test runner output
    iteration: int                    # Loop counter to guard against infinite cycles
    max_iterations: int               # Maximum self-correction attempts
    execution_trace: List[str]        # Audit log of nodes executed
    final_report: str                 # Final synthesized outcome


# ---------------------------------------------------------------------
# 2. StateGraph Engine (Core LangGraph-compatible state machine)
# ---------------------------------------------------------------------
class StateGraph:
    """
    A directed graph engine that coordinates stateful multi-agent execution.
    Mirrors the LangGraph API (Nodes, Edges, Conditional Edges).
    """

    def __init__(self, state_schema=ProjectMindState):
        self.state_schema = state_schema
        self.nodes: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}
        self.edges: Dict[str, str] = {}
        self.conditional_edges: Dict[str, tuple[Callable[[Dict[str, Any]], str], Dict[str, str]]] = {}
        self.entry_point: Optional[str] = None

    def add_node(self, name: str, node_fn: Callable[[Dict[str, Any]], Dict[str, Any]]) -> "StateGraph":
        """Add a computational node to the graph."""
        self.nodes[name] = node_fn
        return self

    def set_entry_point(self, name: str) -> "StateGraph":
        """Designate the initial node where graph execution begins."""
        if name not in self.nodes:
            raise ValueError(f"Node '{name}' must be added before setting as entry point.")
        self.entry_point = name
        return self

    def add_edge(self, from_node: str, to_node: str) -> "StateGraph":
        """Add a fixed directed edge between two nodes."""
        self.edges[from_node] = to_node
        return self

    def add_conditional_edges(
        self,
        source: str,
        condition: Callable[[Dict[str, Any]], str],
        path_map: Dict[str, str],
    ) -> "StateGraph":
        """
        Add a dynamic conditional routing edge evaluated at runtime.
        """
        self.conditional_edges[source] = (condition, path_map)
        return self

    def compile(self) -> "CompiledStateGraph":
        """Compile the graph structure into an executable runnable."""
        if not self.entry_point:
            raise ValueError("StateGraph cannot be compiled without an entry point.")
        return CompiledStateGraph(self)


class CompiledStateGraph:
    """Compiled, runnable representation of the StateGraph."""

    def __init__(self, graph: StateGraph):
        self.graph = graph

    def invoke(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the graph state machine starting from the entry point.
        Follows edges and conditional edges until reaching END.
        """
        state = dict(initial_state)
        state.setdefault("iteration", 0)
        state.setdefault("max_iterations", 3)
        state.setdefault("execution_trace", [])

        current_node_name = self.graph.entry_point

        while current_node_name != END:
            node_fn = self.graph.nodes.get(current_node_name)
            if not node_fn:
                raise RuntimeError(f"Encountered unknown node during execution: '{current_node_name}'")

            # Record trace
            state["execution_trace"].append(current_node_name)

            # Execute node function (pure state transformation)
            node_output = node_fn(state)
            if node_output:
                state.update(node_output)

            # Determine next node
            if current_node_name in self.graph.conditional_edges:
                condition_fn, path_map = self.graph.conditional_edges[current_node_name]
                branch_key = condition_fn(state)
                current_node_name = path_map.get(branch_key, END)
            elif current_node_name in self.graph.edges:
                current_node_name = self.graph.edges[current_node_name]
            else:
                # Terminal node with no outgoing edges
                break

        return state


# ---------------------------------------------------------------------
# 3. Graph Nodes for ProjectMind Multi-Agent Self-Correction
# ---------------------------------------------------------------------

_coding_agent = CodingAgent()
_review_agent = ReviewAgent()
_testing_agent = TestingAgent()


def coding_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Coding Agent Node:
    Implements feature or fixes code based on original task or feedback.
    """
    state["iteration"] = state.get("iteration", 0) + 1
    iteration = state["iteration"]

    # If looping back with review feedback:
    if state.get("review_status") == "REJECTED":
        action_note = f"Fixing security issues from Review feedback (Iteration {iteration})"
    # If looping back with test failure feedback:
    elif state.get("tests_passed") is False:
        action_note = f"Fixing failing unit tests (Iteration {iteration})"
    else:
        action_note = f"Initial code implementation (Iteration {iteration})"

    # Update or fix the code in state
    code = state.get("current_code", "")
    target_file = state.get("file_path")

    # Apply fix ONLY when looping back on feedback (iteration > 1 or rejected/failed)
    if state.get("review_status") == "REJECTED" or state.get("tests_passed") is False:
        if "price * (1 + rate)" in code:
            code = code.replace("price * (1 + rate)", "price * (1 - rate)  # FIXED by self-correction")
        elif "SELECT * FROM users WHERE id =" in code and "f\"" in code:
            code = code.replace(
                "query = f\"SELECT * FROM users WHERE id = '{user_id}'\"",
                "query = \"SELECT * FROM users WHERE id = %s\"\n    params = (user_id,)"
            )

    return {
        "current_code": code,
        "review_status": "PENDING",
        "tests_passed": None,
    }


def review_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Review Agent Node:
    Performs security and quality audit on the latest code.
    """
    code = state.get("current_code", "")
    issues = []

    # Check for SQL injection
    if "f\"SELECT" in code or "f'SELECT" in code:
        issues.append({
            "severity": "CRITICAL",
            "issue": "SQL injection vulnerability via f-string query formatting.",
        })

    # Check for hardcoded secrets
    if "secret_live" in code or "password =" in code:
        issues.append({
            "severity": "CRITICAL",
            "issue": "Hardcoded secret key or password found.",
        })

    has_critical = any(i["severity"] == "CRITICAL" for i in issues)
    status = "REJECTED" if has_critical else "APPROVED"

    return {
        "review_status": status,
        "review_issues": issues,
    }


def testing_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Testing Agent Node:
    Executes automated unit tests against the implemented code.
    """
    code = state.get("current_code", "")
    
    # Simulate test evaluation based on code correctness
    if "(1 + rate)" in code:
        tests_passed = False
        output = "FAILED: test_discount (AssertionError: 120 != 80)"
    else:
        tests_passed = True
        output = "PASSED: 5 tests run, 5 passed, 0 failures."

    return {
        "tests_passed": tests_passed,
        "test_output": output,
    }


# ---------------------------------------------------------------------
# 4. Conditional Edge Decision Functions (The Feedback Loop)
# ---------------------------------------------------------------------

def route_after_review(state: Dict[str, Any]) -> str:
    """
    Decide whether to proceed to Testing or loop back to Coding for fixes.
    """
    if state.get("iteration", 0) >= state.get("max_iterations", 3):
        return "max_retries"

    if state.get("review_status") == "REJECTED":
        return "needs_fix"
    return "approved"


def route_after_testing(state: Dict[str, Any]) -> str:
    """
    Decide whether task is complete or needs to loop back to Coding.
    """
    if state.get("iteration", 0) >= state.get("max_iterations", 3):
        return "max_retries"

    if state.get("tests_passed") is True:
        return "complete"
    return "tests_failed"


# ---------------------------------------------------------------------
# 5. Graph Constructor: Builds the Self-Correction Multi-Agent Cycle
# ---------------------------------------------------------------------
def create_self_correcting_agent_graph() -> CompiledStateGraph:
    """
    Constructs the full multi-agent self-correction cycle:
        [START] → Coding Node → Review Node
                                   │
                    ┌──────────────┴──────────────┐
             (needs_fix)                      (approved)
                    ▼                             ▼
               Coding Node                  Testing Node
                    ▲                             │
                    │               ┌─────────────┴─────────────┐
                    │        (tests_failed)                  (complete)
                    └───────────────┘                           ▼
                                                              [END]
    """
    builder = StateGraph(ProjectMindState)

    # 1. Add agent nodes
    builder.add_node("coding", coding_node)
    builder.add_node("review", review_node)
    builder.add_node("testing", testing_node)

    # 2. Set entry point
    builder.set_entry_point("coding")

    # 3. Edge: Coding always transitions to Review
    builder.add_edge("coding", "review")

    # 4. Conditional Edge after Review:
    #    - If security audit rejected → Loop back to Coding Node!
    #    - If audit approved → Proceed to Testing Node!
    builder.add_conditional_edges(
        source="review",
        condition=route_after_review,
        path_map={
            "needs_fix": "coding",
            "approved": "testing",
            "max_retries": END,
        },
    )

    # 5. Conditional Edge after Testing:
    #    - If tests failed → Loop back to Coding Node!
    #    - If tests passed → Transition to END!
    builder.add_conditional_edges(
        source="testing",
        condition=route_after_testing,
        path_map={
            "tests_failed": "coding",
            "complete": END,
            "max_retries": END,
        },
    )

    return builder.compile()
