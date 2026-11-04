"""
backend/supervisor/supervisor.py
=================================
The Supervisor / Orchestrator — Dynamic Multi-Agent Routing for ProjectMind AI.

HOW IT WORKS:
    1. User submits a request (e.g. "Fix the login bug and run tests").
    2. Intent Classification: The Supervisor analyzes user intent:
       - Direct Memory/Fact lookup (0 agent overhead)
       - Single-Agent routing: CODING, REVIEW, TESTING, or CUSTOM agents
       - Multi-Agent Pipeline: Sequential execution (e.g. Coding → Testing → Review)
    3. Dynamic Orchestration: Dispatches only the required agents.
    4. Synthesis: Consolidates outputs from all stages into a unified executive report.
    5. Agent Builder Integration: Dynamically routes to custom agents built via Phase 20!
"""

import re
import json
from typing import Dict, Any, List, Optional
from backend.agents.base_agent import BaseAgent
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
5. "CUSTOM": For specialized custom agents (e.g. documentation, security audit).
6. "PIPELINE": For multi-step tasks requiring multiple agents (e.g. "fix bug AND run tests").

OUTPUT FORMAT:
Return ONLY a valid JSON object:
{
  "intent": "MEMORY" | "CODING" | "REVIEW" | "TESTING" | "CUSTOM" | "PIPELINE",
  "pipeline": ["coding", "testing"],  // list of agent names to execute in sequence
  "reasoning": "Brief explanation of routing decision"
}
"""


class Supervisor:
    """
    Central orchestrator responsible for analyzing user intent and dynamically
    dispatching specialized built-in and custom agents.
    """

    def __init__(
        self,
        llm_provider: Optional[BaseLLMProvider] = None,
        rag_index: Optional[ProjectRAGIndex] = None,
        load_custom_agents: bool = True,
        use_tier_routing: bool = True,
    ):
        self.rag_index = rag_index or ProjectRAGIndex()
        self.use_tier_routing = use_tier_routing

        if llm_provider is not None:
            # Explicit override (e.g. from tests or caller)
            self.llm = llm_provider
            coding_llm = llm_provider
            review_llm = llm_provider
            testing_llm = llm_provider
        elif use_tier_routing:
            # Phase 22: Task-to-Model Specialization Tiers
            try:
                from backend.llm.model_registry import model_registry
                self.llm = model_registry.get_provider_for_task("routing")
                coding_llm = model_registry.get_provider_for_task("coding")
                review_llm = model_registry.get_provider_for_task("review")
                testing_llm = model_registry.get_provider_for_task("testing")
            except Exception:
                self.llm = get_llm_provider()
                coding_llm = self.llm
                review_llm = self.llm
                testing_llm = self.llm
        else:
            self.llm = get_llm_provider()
            coding_llm = self.llm
            review_llm = self.llm
            testing_llm = self.llm

        # Instantiate built-in specialized agents with their respective tier models
        self.coding_agent = CodingAgent(llm_provider=coding_llm)
        self.review_agent = ReviewAgent(llm_provider=review_llm)
        self.testing_agent = TestingAgent(llm_provider=testing_llm)

        self.agent_registry: Dict[str, BaseAgent] = {
            "coding": self.coding_agent,
            "review": self.review_agent,
            "testing": self.testing_agent,
        }

        # Dynamically load custom agents from AgentBuilder (Phase 20)
        if load_custom_agents:
            self._load_builder_agents()

    def _load_builder_agents(self) -> None:
        """Register custom agents from the global AgentBuilder registry."""
        try:
            from backend.agents.builder import default_agent_builder
            default_agent_builder.register_all_with_supervisor(self)
        except Exception:
            pass

    def register_agent(self, name: str, agent: BaseAgent) -> None:
        """
        Dynamically register a new custom agent with the supervisor at runtime.
        """
        clean_name = name.strip().lower().replace(" ", "_")
        self.agent_registry[clean_name] = agent

    def classify_intent_llm(self, user_prompt: str) -> Dict[str, Any]:
        """
        Use the specialized FAST tier LLM to classify ambiguous queries.
        Falls back to rule-based classify_intent if LLM is unavailable or fails.
        """
        if not self.llm:
            return self.classify_intent(user_prompt)

        try:
            prompt = f"{SUPERVISOR_ROUTER_PROMPT}\n\nUSER REQUEST: {user_prompt}\nRESPONSE (JSON):"
            if hasattr(self.llm, "chat_sync"):
                response = self.llm.chat_sync(prompt)
            else:
                response = None
            if response:
                clean_json = re.search(r"\{.*\}", response, re.DOTALL)
                if clean_json:
                    return json.loads(clean_json.group(0))
        except Exception:
            pass

        return self.classify_intent(user_prompt)

    def classify_intent(self, user_prompt: str) -> Dict[str, Any]:
        """
        Determine the intent and required execution pipeline for a user request.
        Uses fast deterministic classifier patterns, matching custom agent tags and keywords.
        """
        text = user_prompt.lower()
        wants_local = any(k in text for k in ["local", "offline", "private", "air-gapped", "nemotron"])
        target_tier = "local" if wants_local else None

        # 1. Check for Direct Memory questions
        is_memory = any(k in text for k in [
            "what database", "what db", "which framework", "conventions", "tech stack",
            "what llm", "what models", "remembered", "decision", "adr",
            "architecture", "core modules", "project summary", "stored in project memory", "memory facts",
            "course enrollment portal architecture", "course enrollment portal roadmap", "portal roadmap"
        ])
        wants_review = any(k in text for k in ["review", "audit", "security check", "vulnerability"])
        wants_testing = any(k in text for k in ["run test", "run tests", "pytest", "unit test", "test suite"])
        wants_coding = any(k in text for k in ["fix", "bug", "implement", "create function", "refactor", "code", "write"])

        # Check for specialized custom agents (Phase 20)
        wants_docs = any(k in text for k in ["document", "documentation", "docstring", "readme", "api docs"])
        wants_security = any(k in text for k in ["security audit", "vulnerability scan", "cve", "secret leak", "sql injection"])
        wants_devops = any(k in text for k in ["docker", "dockerfile", "ci/cd", "github actions", "deploy script"])

        if is_memory and not (wants_coding or wants_review or wants_docs or wants_security):
            return {
                "intent": "MEMORY",
                "pipeline": ["memory"],
                "reasoning": "Factual question about project architecture or memory.",
            }

        # Match custom agents first if registered
        if wants_docs and "documentation_agent" in self.agent_registry:
            return {
                "intent": "CUSTOM",
                "pipeline": ["documentation_agent"],
                "reasoning": "Documentation request routed to specialized Documentation Agent.",
            }

        if wants_security and "security_auditor" in self.agent_registry:
            return {
                "intent": "CUSTOM",
                "pipeline": ["security_auditor"],
                "reasoning": "Security audit request routed to specialized Security Auditor Agent.",
            }

        if wants_devops and "devops_agent" in self.agent_registry:
            return {
                "intent": "CUSTOM",
                "pipeline": ["devops_agent"],
                "reasoning": "DevOps / containerization task routed to DevOps Agent.",
            }

        # Multi-Agent Pipeline check
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
                "target_tier": target_tier,
                "reasoning": f"Multi-step request requiring collaboration: {' -> '.join(pipeline)}" + (" (executed locally via Nemotron for zero cloud egress)" if wants_local else ""),
            }
        elif len(pipeline) == 1:
            intent_map = {"coding": "CODING", "review": "REVIEW", "testing": "TESTING"}
            return {
                "intent": intent_map[pipeline[0]],
                "pipeline": pipeline,
                "target_tier": target_tier,
                "reasoning": f"Specialized single-agent task routed to {pipeline[0]}." + (" (executed locally via Nemotron for zero cloud egress)" if wants_local else ""),
            }

        # Check any other custom agent registered by name
        for agent_name in self.agent_registry.keys():
            if agent_name not in ("coding", "review", "testing") and agent_name in text:
                return {
                    "intent": "CUSTOM",
                    "pipeline": [agent_name],
                    "reasoning": f"Explicitly named custom agent '{agent_name}'.",
                }

        # Default fallback
        return {
            "intent": "CODING",
            "pipeline": ["coding"],
            "target_tier": target_tier,
            "reasoning": "General development query routed to Coding Agent by default." + (" (executed locally via Nemotron for zero cloud egress)" if wants_local else ""),
        }

    def execute(
        self,
        user_prompt: str,
        session_id: Optional[str] = None,
        persist_run: bool = True,
    ) -> Dict[str, Any]:
        """
        Orchestrate and execute the user's task across the dynamically routed pipeline.
        Optionally persists the run trace to MongoDB Atlas.
        """
        routing_plan = self.classify_intent(user_prompt)
        intent = routing_plan["intent"]
        pipeline = routing_plan["pipeline"]

        # Strategy 1: Direct Memory Route (Zero LLM / Token Overhead)
        if intent == "MEMORY":
            memory_results = tools.search_project_memory(user_prompt, top_k=5)
            formatted_matches = []
            for m in memory_results:
                formatted_matches.append({
                    "key": m.get("key") or m.get("title") or "Fact",
                    "value": m.get("content") or m.get("value") or str(m),
                    "category": m.get("category", "architecture"),
                    "score": m.get("score", 1.0),
                })
            summary = f"Retrieved {len(formatted_matches)} memory facts and decisions directly without invoking agent loops."
            payload = {
                "task": user_prompt,
                "intent": intent,
                "routing_plan": routing_plan,
                "stages_executed": ["memory"],
                "results": {
                    "memory": {
                        "type": "direct_memory_lookup",
                        "matches": formatted_matches,
                    }
                },
                "summary": summary,
                "success": True,
            }

            if persist_run:
                try:
                    from backend.db import repository
                    saved = repository.record_agent_run(
                        task=user_prompt,
                        intent=intent,
                        stages=["memory"],
                        results=payload["results"],
                        summary=summary,
                        success=True,
                        session_id=session_id,
                    )
                    payload["run_id"] = saved.get("run_id")
                except Exception:
                    pass

            return payload

        # Strategy 2: Single-Agent or Multi-Agent Pipeline Execution
        stage_results: Dict[str, Any] = {}
        context_accumulator = user_prompt

        for stage_name in pipeline:
            agent = self.agent_registry.get(stage_name)
            if not agent:
                continue

            # Execute the agent with tier awareness (local Nemotron vs cloud Groq)
            res = agent.run(
                user_prompt=context_accumulator,
                rag_index=self.rag_index,
                tier=routing_plan.get("target_tier"),
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
            f"({' -> '.join(pipeline)}) to complete the task."
        )

        payload = {
            "task": user_prompt,
            "intent": intent,
            "routing_plan": routing_plan,
            "stages_executed": pipeline,
            "results": stage_results,
            "summary": summary,
            "success": True,
        }

        if persist_run:
            try:
                from backend.db import repository
                saved = repository.record_agent_run(
                    task=user_prompt,
                    intent=intent,
                    stages=pipeline,
                    results=stage_results,
                    summary=summary,
                    success=True,
                    session_id=session_id,
                )
                payload["run_id"] = saved.get("run_id")
            except Exception:
                pass

        return payload
