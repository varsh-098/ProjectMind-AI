"""
backend/agents/testing_agent.py
================================
Specialized QA & Testing Agent for ProjectMind AI.

RESPONSIBILITIES:
    - Test suite execution via automated test runners (pytest / unittest)
    - Test failure analysis and root-cause diagnosis
    - Unit test generation covering boundary conditions and edge cases
    - Test coverage assessment against project requirements

TOOLS ACCESSIBLE:
    run_tests, run_command, read_file, create_file, edit_file,
    search_code, recall_fact
"""

from typing import Optional, List, Dict, Any
from backend.agents.base_agent import BaseAgent
from backend.llm.base import BaseLLMProvider
from backend.brain.rag import ProjectRAGIndex
from backend.brain import tools

TESTING_AGENT_PROMPT = """
You are the senior Testing Agent for ProjectMind AI.
Your purpose is to design unit tests, execute test suites, and diagnose test failures.

TESTING PRINCIPLES:
1. TEST PYRAMID & ISOLATION: Focus on fast, isolated unit tests using standard Python
   unittest or pytest frameworks. Use mocks/fixtures for external dependencies.
2. COVERAGE OF EDGE CASES:
   - Null / empty inputs, invalid types, zero division
   - Boundary numbers (0, -1, max values)
   - Expected exceptions (e.g. ValueError, PermissionError)
3. ROOT CAUSE DIAGNOSIS: When tests fail, carefully inspect the stack trace, pinpoint the
   exact failing assertion or unhandled exception, and report the root cause.
4. ACTIONABLE OUTPUT: Format test reports with:
   - Summary of tests run (passed / failed count)
   - Failure analysis
   - Recommended fixes or additional test cases
"""

TESTING_AGENT_TOOLS = [
    "run_tests",
    "run_command",
    "read_file",
    "create_file",
    "edit_file",
    "search_code",
    "recall_fact",
]


class TestingAgent(BaseAgent):
    """Specialized agent dedicated to QA and automated testing."""

    def __init__(
        self,
        llm_provider: Optional[BaseLLMProvider] = None,
        max_turns: int = 5,
    ):
        super().__init__(
            name="Testing Agent",
            role="Autonomous QA & Test Engineering Specialist",
            system_instruction=TESTING_AGENT_PROMPT,
            allowed_tools=TESTING_AGENT_TOOLS,
            llm_provider=llm_provider,
            max_turns=max_turns,
        )

    def execute_and_report(self, test_target: str = "tests") -> Dict[str, Any]:
        """
        Execute a test suite and return structured results.
        """
        raw_result = tools.execute_tool("run_tests", {"test_target": test_target})
        if not raw_result["success"]:
            return {
                "test_target": test_target,
                "passed": False,
                "summary": f"Failed to execute test runner: {raw_result['error']}",
                "output": "",
            }

        data = raw_result["result"]
        return {
            "test_target": test_target,
            "passed": data["passed"],
            "exit_code": data["exit_code"],
            "output": data["output"],
            "status": "PASSED" if data["passed"] else "FAILED",
        }

    def generate_tests_for_file(
        self,
        source_path: str,
        test_path: Optional[str] = None,
        rag_index: Optional[ProjectRAGIndex] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a source file and generate a unit test suite for it.
        """
        content = tools.read_file(source_path, with_line_numbers=True)
        target_dest = test_path or f"tests/test_{source_path.split('/')[-1]}"

        prompt = (
            f"Generate a comprehensive unit test suite using unittest.TestCase for:\n"
            f"File: '{source_path}'\n\n"
            f"```python\n{content}\n```\n\n"
            f"Write the test code and save it to '{target_dest}' using 'create_file'. "
            "Then run the tests using 'run_tests' to verify they pass."
        )
        return self.run(user_prompt=prompt, rag_index=rag_index)

    def diagnose_failure(self, failure_trace: str) -> Dict[str, Any]:
        """Diagnose a test failure trace and suggest remedies."""
        prompt = (
            "Analyze the following test failure traceback:\n\n"
            f"```\n{failure_trace}\n```\n\n"
            "Identify the root cause, the exact failing assertion, and recommend a code fix."
        )
        return self.run(user_prompt=prompt)
