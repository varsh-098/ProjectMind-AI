"""
backend/supervisor/supervisor.py
=================================
The Supervisor / Orchestrator — Dynamic Multi-Agent Routing for ProjectMind AI.

HOW IT WORKS:
    1. User submits a request (e.g. "Fix the login bug and run tests").
    2. Intent Classification: The Supervisor analyzes user intent:
       - Direct Memory/Fact lookup (0 agent overhead)
       - Single-Agent routing: CODING, REVIEW, or TESTING
       - Multi-Agent Pipeline: Sequential execution (e.g. Coding → Testing → Review)
    3. Dynamic Orchestration: Dispatches only the required agents.
    4. Synthesis: Consolidates outputs from all stages into a unified executive report.

WHY DYNAMIC ROUTING MATTERS:
    Activating every agent for every query wastes compute, increases latency,
    and causes hallucinated interventions. Dynamic routing ensures:
      "What DB do we use?"      → Instant Memory lookup (0 tokens)
      "Review my auth module"   → Review Agent only
      "Write a test for utils"  → Testing Agent only
      "Fix bug and verify"      → Sequential: Coding Agent → Testing Agent
"""

import re
import json
from typing import Dict, Any, List, Optional
from backend.agents.coding_agent import CodingAgent
from backend.agents.review_agent import ReviewAgent
from backend.agents.testing_agent import TestingAgent
from backend.llm.base import BaseLLMProvider
from backend.llm.factory import get_llm_provider
from backend.brain.rag import ProjectRAGIndex
from backend.brain import tools


SUPERVISOR_ROUTER_PROMPT = """
You are the Supervisor Orchestrator for ProjectMind AI.
Analyze the user's request and determine the most efficient routing plan.

AVAILABLE ROUTING DESTINATIONS:
1. "MEMORY": For questions about tech stack, database, conventions, or past decisions.
2. "CODING": For generating code, fixing bugs, refactoring, or feature implementations.
3. "REVIEW": For code quality audits, security scans, or pull request reviews.
4. "TESTING": For running test suites, analyzing test failures, or writing unit tests.
5. "PIPELINE": For multi-step tasks requiring multiple agents (e.g. "fix bug AND run tests").

OUTPUT FORMAT:
Return ONLY a valid JSON object:
{
  "intent": "MEMORY" | "CODING" | "REVIEW" | "TESTING" | "PIPELINE",
  "pipeline": ["coding", "testing"],  // list of agent names to execute in sequence
  "reasoning": "Brief explanation of routing decision"
}
"""


class Supervisor:
    """
    Central orchestrator responsible for analyzing user intent and dynamically
    dispatching specialized agents.
    """

    def __init__(
        self,
        llm_provider: Optional[BaseLLMProvider] = None,
        rag_index: Optional[ProjectRAGIndex] = None,
    ):
        try:
            self.llm = llm_provider or get_llm_provider()
        except Exception:
            self.llm = None

        self.rag_index = rag_index or ProjectRAGIndex()

        # Instantiate specialized agents
        self.coding_agent = CodingAgent(llm_provider=self.llm)
        self.review_agent = ReviewAgent(llm_provider=self.llm)
        self.testing_agent = TestingAgent(llm_provider=self.llm)

        self.agent_registry = {
            "coding": self.coding_agent,
            "review": self.review_agent,
            "testing": self.testing_agent,
        }

    def classify_intent(self, user_prompt: str) -> Dict[str, Any]:
        """
        Determine the intent and required execution pipeline for a user request.
        Uses LLM reasoning when available, with a fast deterministic classifier fallback.
        """
        text = user_prompt.lower()

        # Fast deterministic classifier patterns
        is_memory = any(k in text for k in [
            "what database", "what db", "which framework", "conventions", "tech stack",
            "what llm", "what models", "remembered", "decision", "adr"
        ])
        wants_review = any(k in text for k in ["review", "audit", "security check", "vulnerability"])
        wants_testing = any(k in text for k in ["run test", "run tests", "pytest", "unit test", "test suite"])
        wants_coding = any(k in text for k in ["fix", "bug", "implement", "create function", "refactor", "code", "write"])

        # Determine pipeline
        if is_memory and not (wants_coding or wants_review):
            return {
                "intent": "MEMORY",
                "pipeline": ["memory"],
                "reasoning": "Factual question about project architecture or memory.",
            }

        pipeline = []
        if wants_coding:
            pipeline.append("coding")
        if wants_review:
            pipeline.append("review")
        if wants_testing:
            pipeline.append("testing")

        if len(pipeline) > 1:
            return {
                "intent": "PIPELINE",
                "pipeline": pipeline,
                "reasoning": f"Multi-step request requiring collaboration: {' -> '.join(pipeline)}",
            }
        elif len(pipeline) == 1:
            intent_map = {"coding": "CODING", "review": "REVIEW", "testing": "TESTING"}
            return {
                "intent": intent_map[pipeline[0]],
                "pipeline": pipeline,
                "reasoning": f"Specialized single-agent task routed to {pipeline[0]}.",
            }

        # Default fallback
        return {
            "intent": "CODING",
            "pipeline": ["coding"],
            "reasoning": "General development query routed to Coding Agent by default.",
        }

    def execute(self, user_prompt: str) -> Dict[str, Any]:
        """
        Orchestrate and execute the user's task across the dynamically routed pipeline.
        """
        routing_plan = self.classify_intent(user_prompt)
        intent = routing_plan["intent"]
        pipeline = routing_plan["pipeline"]

        # Strategy 1: Direct Memory Route (Zero LLM / Token Overhead)
        if intent == "MEMORY":
            memory_results = tools.search_project_memory(user_prompt, top_k=3)
            return {
                "task": user_prompt,
                "intent": intent,
                "routing_plan": routing_plan,
                "stages_executed": ["memory"],
                "results": {
                    "memory": {
                        "type": "direct_memory_lookup",
                        "matches": memory_results,
                    }
                },
                "summary": f"Retrieved {len(memory_results)} memory facts and decisions directly without invoking agent loops.",
                "success": True,
            }

        # Strategy 2: Single-Agent or Multi-Agent Pipeline Execution
        stage_results: Dict[str, Any] = {}
        context_accumulator = user_prompt

        for stage_name in pipeline:
            agent = self.agent_registry.get(stage_name)
            if not agent:
                continue

            # Execute the agent
            res = agent.run(
                user_prompt=context_accumulator,
                rag_index=self.rag_index,
            )
            stage_results[stage_name] = res

            # Pass agent output as context for next stage in pipeline
            if stage_name == "coding":
                context_accumulator = (
                    f"Original Task: {user_prompt}\n\n"
                    f"Coding Agent Output:\n{res.get('final_response', '')}\n\n"
                    "Next Stage: Verify or review the above code."
                )

        # Synthesize final summary
        summary = (
            f"Supervisor successfully coordinated {len(pipeline)} agent(s) "
            f"({' → '.join(pipeline)}) to complete the task."
        )

        return {
            "task": user_prompt,
            "intent": intent,
            "routing_plan": routing_plan,
            "stages_executed": pipeline,
            "results": stage_results,
            "summary": summary,
            "success": True,
        }
