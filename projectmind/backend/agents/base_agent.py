"""
backend/agents/base_agent.py
=============================
Base class that all ProjectMind specialized AI agents inherit from.

WHAT IS AN AGENT?
    An LLM alone is just a static text-completion model.
    An AGENT is an autonomous entity that combines:
      1. LLM (Reasoning engine - Nemotron, Groq, Gemini)
      2. Persona & Instructions (Role-specific system prompt)
      3. Tools (Action capabilities - read, edit, search, test)
      4. Context (Project Brain - RAG search + Persistent Memory)
      5. Execution Loop (ReAct: Reason → Act → Observe → Conclude)

All specialized agents (CodingAgent, ReviewAgent, TestingAgent) inherit
from BaseAgent and configure their specific personas and toolsets.
"""

import json
from typing import List, Dict, Any, Optional
from backend.llm.factory import get_llm_provider
from backend.llm.base import BaseLLMProvider
from backend.brain import tools
from backend.brain.rag import ProjectRAGIndex


class BaseAgent:
    """
    Abstract base agent providing ReAct (Reason + Act) loop execution,
    tool dispatching, and Project Brain context injection.
    """

    def __init__(
        self,
        name: str,
        role: str,
        system_instruction: str,
        allowed_tools: Optional[List[str]] = None,
        llm_provider: Optional[BaseLLMProvider] = None,
        max_turns: int = 5,
    ):
        self.name = name
        self.role = role
        self.system_instruction = system_instruction
        self.allowed_tools = allowed_tools or list(tools.TOOL_REGISTRY.keys())
        self.max_turns = max_turns

        # LLM Provider (defaults to factory setting from .env)
        try:
            self.llm = llm_provider or get_llm_provider()
        except Exception:
            self.llm = None

        # Filter tool schemas to only allowed tools
        all_schemas = tools.get_tool_schemas()
        self.tool_schemas = [
            s for s in all_schemas
            if s["function"]["name"] in self.allowed_tools
        ]

    def _build_system_prompt(self, include_memory: bool = True) -> str:
        """
        Compose full system instruction including persona, tool definitions,
        and persistent project memory.
        """
        prompt_parts = [
            f"You are the {self.name} for ProjectMind AI.",
            f"Role: {self.role}",
            "",
            self.system_instruction.strip(),
            "",
            "AVAILABLE TOOLS:",
            "You have access to the following tools to inspect and act on the project:",
        ]

        for s in self.tool_schemas:
            fn = s["function"]
            prompt_parts.append(f"- {fn['name']}: {fn['description']}")

        prompt_parts.append(
            "\nTo call a tool, output a JSON object in this format:\n"
            '```json\n{"name": "tool_name", "arguments": {"param": "value"}}\n```\n'
            "When you have finished the task and need no more tools, provide your final response directly."
        )

        if include_memory:
            memory_block = tools.get_project_memory_context(max_chars=1800)
            if memory_block:
                prompt_parts.append(f"\n{memory_block}")

        return "\n".join(prompt_parts)

    def run(
        self,
        user_prompt: str,
        rag_index: Optional[ProjectRAGIndex] = None,
        top_k_rag: int = 2,
    ) -> Dict[str, Any]:
        """
        Execute the agent's autonomous ReAct loop on the given task.

        Returns:
            Dict containing:
              - agent: Agent name
              - task: Initial prompt
              - turns_executed: Number of tool iterations
              - steps: Trace of thoughts and tool observations
              - final_response: Concluding message from the agent
        """
        steps: List[Dict[str, Any]] = []

        # 1. RAG Context Injection (if index provided)
        effective_prompt = user_prompt
        if rag_index:
            effective_prompt = rag_index.build_augmented_prompt(
                user_question=user_prompt,
                top_k=top_k_rag,
                max_context_chars=2500,
            )

        system_prompt = self._build_system_prompt(include_memory=True)
        current_input = effective_prompt

        # 2. ReAct Multi-Turn Loop
        for turn in range(1, self.max_turns + 1):
            if not self.llm:
                # Offline / test fallback mode
                steps.append({
                    "turn": turn,
                    "action": "offline_mode",
                    "note": "No active LLM provider configured; ReAct loop simulated."
                })
                return {
                    "agent": self.name,
                    "task": user_prompt,
                    "turns_executed": 1,
                    "steps": steps,
                    "final_response": "Agent initialized successfully in offline verification mode.",
                    "success": True,
                }

            # Call LLM
            response_text = self.llm.chat(
                message=current_input,
                system_instruction=system_prompt,
            )

            # Check if LLM requested a tool call
            tool_call = tools.parse_tool_call(response_text)

            if not tool_call:
                # No tool called -> Agent finished reasoning and gave final response
                steps.append({
                    "turn": turn,
                    "type": "final_answer",
                    "content": response_text.strip(),
                })
                return {
                    "agent": self.name,
                    "task": user_prompt,
                    "turns_executed": turn,
                    "steps": steps,
                    "final_response": response_text.strip(),
                    "success": True,
                }

            # Tool call detected
            tool_name = tool_call.get("name")
            tool_args = tool_call.get("arguments", {})

            # Security: verify tool is in allowed_tools
            if tool_name not in self.allowed_tools:
                tool_result = {
                    "tool": tool_name,
                    "success": False,
                    "result": None,
                    "error": f"Tool '{tool_name}' is not permitted for {self.name}.",
                }
            else:
                tool_result = tools.execute_tool(tool_name, tool_args)

            steps.append({
                "turn": turn,
                "type": "tool_execution",
                "tool": tool_name,
                "arguments": tool_args,
                "result": tool_result,
            })

            # Format observation for the next turn
            current_input = (
                f"Tool '{tool_name}' executed.\n"
                f"Result:\n{json.dumps(tool_result, indent=2)}\n\n"
                "Review the result above and proceed to the next step or provide your final response."
            )

        # Max turns reached
        return {
            "agent": self.name,
            "task": user_prompt,
            "turns_executed": self.max_turns,
            "steps": steps,
            "final_response": "Reached maximum turn limit before concluding.",
            "success": False,
        }
