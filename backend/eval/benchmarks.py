"""
backend/eval/benchmarks.py
==========================
Phase 25: Evaluation & Benchmarking — Standard Benchmark Tasks & Suites.

PURPOSE:
    Defines standardized benchmark tasks across 5 core AI agent capabilities:
      1. Coding: Code generation, syntax correctness, and structural integrity.
      2. Review: Vulnerability detection, static analysis, and false-positive prevention.
      3. Testing: Unit test generation, assertion coverage, and failure diagnosis.
      4. Orchestration: Supervisor multi-agent intent classification and routing.
      5. Memory: Persistent project facts and architectural knowledge retrieval.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


class BenchmarkCategory(str, Enum):
    CODING = "coding"
    REVIEW = "review"
    TESTING = "testing"
    ORCHESTRATION = "orchestration"
    MEMORY = "memory"


@dataclass
class BenchmarkTask:
    """A single standardized evaluation task."""
    id: str
    name: str
    category: BenchmarkCategory
    description: str
    prompt: str
    expected_tools: List[str] = field(default_factory=list)
    assertions: Dict[str, Any] = field(default_factory=dict)
    mock_response: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "prompt": self.prompt,
            "expected_tools": self.expected_tools,
            "assertions": self.assertions,
        }


@dataclass
class BenchmarkSuite:
    """A collection of related benchmark tasks."""
    name: str
    category: BenchmarkCategory
    description: str
    tasks: List[BenchmarkTask] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "task_count": len(self.tasks),
            "tasks": [t.to_dict() for t in self.tasks],
        }


# =========================================================================
# 1. CODING BENCHMARK SUITE
# =========================================================================
CODING_TASKS = [
    BenchmarkTask(
        id="code_lru_cache",
        name="LRU Cache Implementation",
        category=BenchmarkCategory.CODING,
        description="Generates an object-oriented LRU Cache class with get and put operations.",
        prompt="Write a Python class `LRUCache` that implements an LRU (Least Recently Used) cache with `get(key)` and `put(key, value)` methods using `collections.OrderedDict`.",
        expected_tools=["create_file", "edit_file"],
        assertions={
            "required_classes": ["LRUCache"],
            "required_functions": ["get", "put"],
            "require_valid_syntax": True,
            "require_zero_security_violations": True,
        },
        mock_response=(
            "```python\n"
            "from collections import OrderedDict\n\n"
            "class LRUCache:\n"
            "    \"\"\"Thread-safe, standard LRU Cache implementation.\"\"\"\n"
            "    def __init__(self, capacity: int = 128):\n"
            "        self.capacity = capacity\n"
            "        self.cache = OrderedDict()\n\n"
            "    def get(self, key):\n"
            "        if key not in self.cache:\n"
            "            return None\n"
            "        self.cache.move_to_end(key)\n"
            "        return self.cache[key]\n\n"
            "    def put(self, key, value):\n"
            "        if key in self.cache:\n"
            "            self.cache.move_to_end(key)\n"
            "        self.cache[key] = value\n"
            "        if len(self.cache) > self.capacity:\n"
            "            self.cache.popitem(last=False)\n"
            "```"
        ),
    ),
    BenchmarkTask(
        id="code_binary_search",
        name="Binary Search Function",
        category=BenchmarkCategory.CODING,
        description="Generates a logarithmic binary search algorithm.",
        prompt="Write a Python function `binary_search(arr: list[int], target: int) -> int` that returns the index of target or -1 if not found.",
        expected_tools=[],
        assertions={
            "required_functions": ["binary_search"],
            "require_valid_syntax": True,
            "require_zero_security_violations": True,
        },
        mock_response=(
            "```python\n"
            "def binary_search(arr: list[int], target: int) -> int:\n"
            "    \"\"\"Perform binary search over a sorted integer array.\"\"\"\n"
            "    low, high = 0, len(arr) - 1\n"
            "    while low <= high:\n"
            "        mid = (low + high) // 2\n"
            "        if arr[mid] == target:\n"
            "            return mid\n"
            "        elif arr[mid] < target:\n"
            "            low = mid + 1\n"
            "        else:\n"
            "            high = mid - 1\n"
            "    return -1\n"
            "```"
        ),
    ),
]


# =========================================================================
# 2. REVIEW BENCHMARK SUITE
# =========================================================================
REVIEW_TASKS = [
    BenchmarkTask(
        id="review_eval_injection",
        name="Dynamic Code Execution Review",
        category=BenchmarkCategory.REVIEW,
        description="Reviews vulnerable code containing eval() and identifies critical security risks.",
        prompt=(
            "Review the following Python snippet for security vulnerabilities:\n\n"
            "```python\n"
            "def execute_user_calc(formula_str):\n"
            "    # Evaluates math formula from user\n"
            "    return eval(formula_str)\n"
            "```"
        ),
        expected_tools=[],
        assertions={
            "must_contain_keywords": ["eval", "arbitrary", "injection", "vulnerability"],
            "flagged_critical": True,
        },
        mock_response=(
            "Security Review Finding:\n"
            "- CRITICAL VULNERABILITY: Use of `eval()` in `execute_user_calc` enables arbitrary "
            "code execution / code injection. An attacker can execute arbitrary commands or introspect "
            "the host environment. Recommendation: Use `ast.literal_eval` or a dedicated math parser."
        ),
    ),
    BenchmarkTask(
        id="review_clean_code",
        name="Clean Math Function Review",
        category=BenchmarkCategory.REVIEW,
        description="Verifies that safe, clean code is approved without false positive vulnerabilities.",
        prompt=(
            "Review the following Python snippet for quality and security:\n\n"
            "```python\n"
            "def calculate_average(numbers: list[float]) -> float:\n"
            "    if not numbers:\n"
            "        return 0.0\n"
            "    return sum(numbers) / len(numbers)\n"
            "```"
        ),
        expected_tools=[],
        assertions={
            "must_contain_keywords": ["clean", "safe", "approved", "no security"],
            "must_not_contain_keywords": ["critical vulnerability", "exploit"],
        },
        mock_response=(
            "Code Review Assessment: Approved. Safe and Clean.\n"
            "- No security vulnerabilities found.\n"
            "- Correct handling of empty input edge case.\n"
            "- Clear type annotations and concise logic."
        ),
    ),
]


# =========================================================================
# 3. TESTING BENCHMARK SUITE
# =========================================================================
TESTING_TASKS = [
    BenchmarkTask(
        id="test_gen_string_utils",
        name="Unit Test Suite Generation",
        category=BenchmarkCategory.TESTING,
        description="Generates a standard unittest test case for string utilities.",
        prompt="Write a Python unittest test case `TestStringUtils` that tests `reverse_string` and `is_palindrome`.",
        expected_tools=[],
        assertions={
            "required_classes": ["TestStringUtils"],
            "required_functions": ["test_reverse_string", "test_is_palindrome"],
            "require_valid_syntax": True,
            "require_zero_security_violations": True,
        },
        mock_response=(
            "```python\n"
            "import unittest\n\n"
            "class TestStringUtils(unittest.TestCase):\n"
            "    def test_reverse_string(self):\n"
            "        self.assertEqual(reverse_string('abc'), 'cba')\n"
            "        self.assertEqual(reverse_string(''), '')\n\n"
            "    def test_is_palindrome(self):\n"
            "        self.assertTrue(is_palindrome('racecar'))\n"
            "        self.assertFalse(is_palindrome('project'))\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
            "```"
        ),
    ),
    BenchmarkTask(
        id="test_failure_analysis",
        name="Test Failure Output Diagnosis",
        category=BenchmarkCategory.TESTING,
        description="Parses and diagnoses a failing test trace.",
        prompt=(
            "Diagnose the cause of this test failure output:\n\n"
            "======================================================================\n"
            "FAIL: test_addition (test_math.TestMath.test_addition)\n"
            "----------------------------------------------------------------------\n"
            "Traceback (most recent call last):\n"
            "  File 'test_math.py', line 14, in test_addition\n"
            "    self.assertEqual(add(2, 2), 5)\n"
            "AssertionError: 4 != 5\n"
            "----------------------------------------------------------------------\n"
            "Ran 1 test in 0.001s\n\n"
            "FAILED (failures=1)"
        ),
        expected_tools=[],
        assertions={
            "must_contain_keywords": ["assertionerror", "4", "5", "expected"],
        },
        mock_response=(
            "Test Failure Diagnosis:\n"
            "The test `test_addition` failed because `add(2, 2)` produced `4`, while the test asserted "
            "equality with `5`. The AssertionError `4 != 5` indicates either a faulty test assertion "
            "(expected 4) or an incorrect return value."
        ),
    ),
]


# =========================================================================
# 4. ORCHESTRATION BENCHMARK SUITE
# =========================================================================
ORCHESTRATION_TASKS = [
    BenchmarkTask(
        id="orch_route_coding",
        name="Coding Intent Routing",
        category=BenchmarkCategory.ORCHESTRATION,
        description="Evaluates Supervisor intent classification for code generation requests.",
        prompt="Write a FastAPI endpoint for user profile updates with password validation.",
        expected_tools=[],
        assertions={
            "expected_intent": "CODING",
        },
        mock_response='{"intent": "CODING", "pipeline": ["coding"], "reasoning": "User requested writing code for an endpoint."}',
    ),
    BenchmarkTask(
        id="orch_route_pipeline",
        name="Multi-Agent Pipeline Routing",
        category=BenchmarkCategory.ORCHESTRATION,
        description="Evaluates Supervisor multi-step routing for complex tasks (code + test).",
        prompt="Refactor the authentication token verification logic and run the unit test suite to verify.",
        expected_tools=[],
        assertions={
            "expected_intent": "PIPELINE",
            "expected_pipeline": ["coding", "testing"],
        },
        mock_response='{"intent": "PIPELINE", "pipeline": ["coding", "testing"], "reasoning": "Task involves refactoring code and running test suites."}',
    ),
    BenchmarkTask(
        id="orch_route_memory",
        name="Memory Intent Routing",
        category=BenchmarkCategory.ORCHESTRATION,
        description="Evaluates Supervisor intent routing for architectural memory lookups.",
        prompt="What database does ProjectMind AI use for persisting user sessions?",
        expected_tools=[],
        assertions={
            "expected_intent": "MEMORY",
        },
        mock_response='{"intent": "MEMORY", "pipeline": [], "reasoning": "User asked for architectural technology stack memory."}',
    ),
]


# =========================================================================
# 5. MEMORY BENCHMARK SUITE
# =========================================================================
MEMORY_TASKS = [
    BenchmarkTask(
        id="memory_tech_stack_recall",
        name="Tech Stack Knowledge Recall",
        category=BenchmarkCategory.MEMORY,
        description="Verifies accurate recall of project architecture and dependencies.",
        prompt="List the primary database, authentication mechanism, and backend framework used in ProjectMind AI.",
        expected_tools=[],
        assertions={
            "expected_facts": [
                "MongoDB Atlas",
                "Argon2id and HttpOnly session cookies",
                "FastAPI with Pydantic",
            ],
        },
        mock_response=(
            "ProjectMind AI Architecture Facts:\n"
            "- Database: MongoDB Atlas (with motor async driver and MongoDBManager pool)\n"
            "- Authentication: Argon2id password hashing and 256-bit HttpOnly session cookies with CSRF validation\n"
            "- Backend Framework: FastAPI with Pydantic settings and models"
        ),
    ),
]


# =========================================================================
# SUITE REGISTRY
# =========================================================================
ALL_SUITES: Dict[str, BenchmarkSuite] = {
    "coding": BenchmarkSuite(
        name="Coding Suite",
        category=BenchmarkCategory.CODING,
        description="Evaluates code generation, syntax correctness, and class/function structures.",
        tasks=CODING_TASKS,
    ),
    "review": BenchmarkSuite(
        name="Review Suite",
        category=BenchmarkCategory.REVIEW,
        description="Evaluates vulnerability identification and false-positive prevention.",
        tasks=REVIEW_TASKS,
    ),
    "testing": BenchmarkSuite(
        name="Testing Suite",
        category=BenchmarkCategory.TESTING,
        description="Evaluates unit test generation, failure analysis, and assertion coverage.",
        tasks=TESTING_TASKS,
    ),
    "orchestration": BenchmarkSuite(
        name="Orchestration Suite",
        category=BenchmarkCategory.ORCHESTRATION,
        description="Evaluates Supervisor intent classification and multi-agent pipeline routing.",
        tasks=ORCHESTRATION_TASKS,
    ),
    "memory": BenchmarkSuite(
        name="Memory Suite",
        category=BenchmarkCategory.MEMORY,
        description="Evaluates persistent project memory recall and architecture fidelity.",
        tasks=MEMORY_TASKS,
    ),
}


def get_benchmark_suite(name: str) -> Optional[BenchmarkSuite]:
    """Retrieve a benchmark suite by name ('coding', 'review', etc.)."""
    return ALL_SUITES.get(name.lower())


def list_benchmark_suites() -> List[Dict[str, Any]]:
    """Return catalog metadata for all registered benchmark suites."""
    return [suite.to_dict() for suite in ALL_SUITES.values()]


def get_all_tasks() -> List[BenchmarkTask]:
    """Return a flat list of all benchmark tasks across all suites."""
    tasks = []
    for suite in ALL_SUITES.values():
        tasks.extend(suite.tasks)
    return tasks
