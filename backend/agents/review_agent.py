"""
backend/agents/review_agent.py
===============================
Specialized Code Review & Security Agent for ProjectMind AI.

RESPONSIBILITIES:
    - Static security auditing (vulnerability detection, hardcoded secrets, injection)
    - Code quality & design pattern compliance
    - Severity-rated issue classification: CRITICAL, WARNING, SUGGESTION
    - Adherence to project conventions defined in Project Memory

TOOLS ACCESSIBLE:
    read_file, search_code, list_files, get_project_summary,
    recall_fact, search_project_memory
    (Note: Review Agent has READ-ONLY access to ensure separation of concerns)
"""

import json
from typing import Optional, List, Dict, Any
from backend.agents.base_agent import BaseAgent
from backend.llm.base import BaseLLMProvider
from backend.brain.rag import ProjectRAGIndex
from backend.brain import tools

REVIEW_AGENT_PROMPT = """
You are the senior Review Agent for ProjectMind AI.
Your purpose is to conduct rigorous code reviews and security audits.

REVIEW CRITERIA:
1. SECURITY (CRITICAL):
   - SQL / command injection, path traversal, auth bypass
   - Hardcoded passwords, API keys, secrets, or tokens
   - Insecure deserialization, unvalidated input
2. RELIABILITY & ROBUSTNESS (WARNING):
   - Resource leaks (unclosed files, database connections, sockets)
   - Unhandled exceptions, DivisionByZero, NullReference / NoneType crashes
   - Race conditions and improper concurrency handling
3. QUALITY & MAINTAINABILITY (SUGGESTION):
   - Type annotations, docstrings, variable naming conventions
   - Dead code, unnecessary complexity, code duplication
   - Adherence to conventions stored in project memory (e.g. Black / Ruff style)

STRUCTURED OUTPUT FORMAT:
Always format your review findings as a valid JSON object:
{
  "summary": "Brief 1-2 sentence overall assessment",
  "approved": true/false,
  "issues": [
    {
      "severity": "CRITICAL" | "WARNING" | "SUGGESTION",
      "line": 12,
      "issue": "Description of the problem",
      "fix": "Specific recommended remediation"
    }
  ]
}
"""

REVIEW_AGENT_TOOLS = [
    "read_file",
    "search_code",
    "list_files",
    "get_project_summary",
    "recall_fact",
    "search_project_memory",
]


class ReviewAgent(BaseAgent):
    """Specialized agent dedicated to code review and security audits."""

    def __init__(
        self,
        llm_provider: Optional[BaseLLMProvider] = None,
        max_turns: int = 4,
    ):
        super().__init__(
            name="Review Agent",
            role="Senior Code Quality & Security Auditor",
            system_instruction=REVIEW_AGENT_PROMPT,
            allowed_tools=REVIEW_AGENT_TOOLS,
            llm_provider=llm_provider,
            max_turns=max_turns,
        )

    def review_file(
        self,
        file_path: str,
        rag_index: Optional[ProjectRAGIndex] = None,
    ) -> Dict[str, Any]:
        """
        Review an existing project file for bugs and security vulnerabilities.
        """
        content = tools.read_file(file_path, with_line_numbers=True)
        prompt = (
            f"Review the following source file: '{file_path}'\n\n"
            f"```python\n{content}\n```\n\n"
            "Inspect the code against security, reliability, and project memory standards. "
            "Output your findings in the required JSON review format."
        )
        return self.run(user_prompt=prompt, rag_index=rag_index)

    def review_code_snippet(self, code: str, title: str = "Snippet") -> Dict[str, Any]:
        """Review an in-memory code snippet."""
        prompt = (
            f"Review the following code snippet ({title}):\n\n"
            f"```python\n{code}\n```\n\n"
            "Provide severity-rated findings in the required JSON review format."
        )
        return self.run(user_prompt=prompt)
