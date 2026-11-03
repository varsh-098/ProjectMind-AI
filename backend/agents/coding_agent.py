"""
backend/agents/coding_agent.py
===============================
Specialized Coding Agent for ProjectMind AI.

RESPONSIBILITIES:
    - Code inspection and architectural analysis
    - Surgical bug fixing using exact text replacement
    - New feature and module implementation
    - Test execution to verify fixes and avoid regressions

TOOLS ACCESSIBLE:
    read_file, edit_file, create_file, search_code, list_files,
    get_project_summary, recall_fact, run_tests
"""

from typing import Optional, List, Dict, Any
from backend.agents.base_agent import BaseAgent
from backend.llm.base import BaseLLMProvider
from backend.brain.rag import ProjectRAGIndex

CODING_AGENT_PROMPT = """
You are the senior Coding Agent for ProjectMind AI.
Your purpose is to write programs, implement features, and surgically fix bugs.

CRITICAL OPERATIONAL RULES:
1. DIRECT CODE GENERATION FOR STANDALONE TASKS: If the user requests a standalone program, script, algorithm, test, or explanation (e.g., palindrome check, calculator, sorting algorithm, data structures), directly output the complete, elegant, and working code with explanations. Do NOT call tools like 'list_files' or search the codebase when asked to write standalone scripts.
2. INVESTIGATE BEFORE EDITING PROJECT FILES: For tasks modifying existing project files, inspect the codebase using 'search_code' or 'read_file' before proposing or applying changes.
3. SURGICAL EDITS: When modifying existing files, call 'edit_file' with exact code matching. Include enough surrounding context to ensure the target string is unique.
4. MODULAR IMPLEMENTATIONS: Use 'create_file' when asked to introduce or save new project files.
5. VERIFY WITH TESTS: After editing or writing project code, invoke 'run_tests' to verify changes.
6. RESPECT PROJECT MEMORY: Adhere to architecture rules and conventions defined in project memory.
"""

CODING_AGENT_TOOLS = [
    "read_file",
    "edit_file",
    "create_file",
    "search_code",
    "list_files",
    "get_project_summary",
    "recall_fact",
    "run_tests",
]


class CodingAgent(BaseAgent):
    """Autonomous agent dedicated to software engineering tasks."""

    def __init__(
        self,
        llm_provider: Optional[BaseLLMProvider] = None,
        max_turns: int = 6,
    ):
        super().__init__(
            name="Coding Agent",
            role="Autonomous Software Engineer",
            system_instruction=CODING_AGENT_PROMPT,
            allowed_tools=CODING_AGENT_TOOLS,
            llm_provider=llm_provider,
            max_turns=max_turns,
        )

    def fix_bug(
        self,
        file_path: str,
        bug_description: str,
        rag_index: Optional[ProjectRAGIndex] = None,
    ) -> Dict[str, Any]:
        """Convenience method to dispatch a bug-fixing task."""
        prompt = (
            f"Fix the following bug in '{file_path}':\n"
            f"{bug_description}\n\n"
            "Steps to follow:\n"
            "1. Read the affected file to inspect the bug.\n"
            "2. Apply a surgical fix using edit_file.\n"
            "3. Run unit tests using run_tests to verify your fix."
        )
        return self.run(user_prompt=prompt, rag_index=rag_index)

    def implement_feature(
        self,
        feature_description: str,
        target_path: str,
        rag_index: Optional[ProjectRAGIndex] = None,
    ) -> Dict[str, Any]:
        """Convenience method to implement a new feature or file."""
        prompt = (
            f"Implement the requested feature at '{target_path}':\n"
            f"{feature_description}\n\n"
            "Steps:\n"
            "1. Inspect surrounding architecture using search_code or read_file.\n"
            "2. Write clean, modular code using create_file or edit_file.\n"
            "3. Verify your implementation."
        )
        return self.run(user_prompt=prompt, rag_index=rag_index)
