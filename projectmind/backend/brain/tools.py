"""
backend/brain/tools.py
=======================
Tools that AI agents use to inspect and interact with the project.

WHY TOOLS MATTER:
    Without tools, an agent can only THINK (generate text).
    With tools, an agent can ACT:
      - Read and search project files (Phase 10)
      - Access persistent facts & architectural memory (Phase 13)
      - Modify code, run tests, and execute commands safely (Phase 14)
      - Report structured tool execution output back to the model

Phase 10: File & Code Access Tools
Phase 13: Project Memory Tools
Phase 14: Agent Action Tools & Function Calling Schemas
"""

import os
import re
import sys
import json
import subprocess
from typing import Any, Optional, List, Dict
from backend.brain.file_manager import ProjectFileManager
from backend.brain.memory import ProjectMemoryManager

# Singleton instances for tool calls
_file_manager = ProjectFileManager()
_memory_manager = ProjectMemoryManager()


# =====================================================================
# Phase 10: File Access Tools
# =====================================================================

def read_file(
    path: str,
    start_line: int = 1,
    end_line: int | None = None,
    with_line_numbers: bool = False,
) -> str:
    """Read the contents of a project file."""
    return _file_manager.read_file(
        filepath=path,
        start_line=start_line,
        end_line=end_line,
        with_line_numbers=with_line_numbers,
    )


def list_files(subpath: str = "") -> list[dict[str, Any]]:
    """List all indexed source files in the project."""
    return _file_manager.list_files(subpath=subpath)


def get_project_tree(subpath: str = "", max_depth: int = 4) -> str:
    """Get an ASCII representation of the project's folder structure."""
    return _file_manager.get_tree(subpath=subpath, max_depth=max_depth)


def search_code(
    query: str,
    case_sensitive: bool = False,
    max_matches: int = 50,
) -> list[dict[str, Any]]:
    """Search for a text pattern or symbol across all project files (Grep)."""
    return _file_manager.search_code(
        query=query,
        case_sensitive=case_sensitive,
        max_matches=max_matches,
    )


def get_project_summary() -> dict[str, Any]:
    """Get overall statistics about the project."""
    return _file_manager.get_summary()


# =====================================================================
# Phase 13: Project Memory Tools
# =====================================================================

def remember_fact(
    key: str,
    value: str,
    category: str = "general",
    tags: Optional[List[str]] = None,
) -> dict[str, Any]:
    """Store a permanent fact in ProjectMind's persistent memory."""
    return _memory_manager.add_fact(key=key, value=value, category=category, tags=tags)


def recall_fact(key: str) -> Optional[dict[str, Any]]:
    """Retrieve a specific fact by key from persistent memory."""
    return _memory_manager.get_fact(key=key)


def list_project_facts(
    category: Optional[str] = None,
    tag: Optional[str] = None,
) -> list[dict[str, Any]]:
    """List stored facts, optionally filtered by category or tag."""
    return _memory_manager.list_facts(category=category, tag=tag)


def record_project_decision(
    title: str,
    description: str,
    rationale: str = "",
    tags: Optional[List[str]] = None,
) -> dict[str, Any]:
    """Record an architectural decision (ADR) in persistent memory."""
    return _memory_manager.record_decision(
        title=title,
        description=description,
        rationale=rationale,
        tags=tags,
    )


def list_project_decisions() -> list[dict[str, Any]]:
    """List all architectural decisions stored in memory."""
    return _memory_manager.list_decisions()


def search_project_memory(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Semantically search facts and decisions using vector similarity."""
    return _memory_manager.search_memory(query=query, top_k=top_k)


def get_project_memory_context(
    max_chars: int = 2500,
    category: Optional[str] = None,
) -> str:
    """Build a formatted memory context block ready to inject into the LLM prompt."""
    return _memory_manager.get_memory_context_block(max_chars=max_chars, category=category)


def get_memory_stats() -> dict[str, Any]:
    """Get stats about total facts, decisions, and categories."""
    return _memory_manager.stats()


# =====================================================================
# Phase 14: Action & Execution Tools
# =====================================================================

def create_file(path: str, content: str, overwrite: bool = False) -> dict[str, Any]:
    """
    Create a new source or configuration file within project boundaries.

    Args:
        path: Path relative to the project root.
        content: Text content to write into the file.
        overwrite: Whether to overwrite if the file already exists.
    """
    return _file_manager.create_file(filepath=path, content=content, overwrite=overwrite)


def edit_file(path: str, old_str: str, new_str: str) -> dict[str, Any]:
    """
    Perform a surgical text replacement within an existing file.

    Args:
        path: Path relative to the project root.
        old_str: The exact target string to be replaced.
        new_str: The replacement string.
    """
    return _file_manager.edit_file(filepath=path, old_str=old_str, new_str=new_str)


# Dangerous shell commands blocked for safety
BLOCKED_COMMAND_PATTERNS = [
    r"\brm\s+-[rf]{1,2}\b",
    r"\bdel\s+/[fqsb]{1,4}\b",
    r"\bformat\b",
    r"\bmkfs\b",
    r":\(\)\s*\{\s*:\|:&\s*\};:",
    r"\bshutdown\b",
    r"\breboot\b",
]


def run_command(command: str, timeout: int = 30) -> dict[str, Any]:
    """
    Safely execute a shell command inside the project root directory.

    Args:
        command: Command line string to execute (e.g. 'git status', 'python --version').
        timeout: Maximum duration in seconds before killing the process.
    """
    # Guard against destructive commands
    for pattern in BLOCKED_COMMAND_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return {
                "command": command,
                "exit_code": 1,
                "stdout": "",
                "stderr": f"Security restriction: Command matched blocked pattern '{pattern}'.",
                "success": False,
            }

    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(_file_manager.root_path),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "command": command,
            "exit_code": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "success": proc.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {
            "command": command,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Execution timed out after {timeout} seconds.",
            "success": False,
        }
    except Exception as e:
        return {
            "command": command,
            "exit_code": 1,
            "stdout": "",
            "stderr": str(e),
            "success": False,
        }


def run_tests(test_target: str = "tests", timeout: int = 60) -> dict[str, Any]:
    """
    Run the project test suite using pytest, falling back to Python's built-in unittest runner.

    Args:
        test_target: Test path or specific test file (e.g. 'tests', 'tests/test_memory.py').
        timeout: Execution timeout in seconds.
    """
    python_bin = sys.executable

    # Format command: test if pytest is installed, otherwise use standard library unittest
    clean_target = test_target.replace("\\", "/").rstrip("/")
    if clean_target.endswith(".py"):
        unit_target = clean_target
    else:
        unit_target = f"discover -s {clean_target} -p 'test_*.py'"

    cmd = (
        f'"{python_bin}" -c "import pytest" 2>nul && '
        f'"{python_bin}" -m pytest {clean_target} -v --tb=short || '
        f'"{python_bin}" -m unittest {unit_target}'
    )

    result = run_command(command=cmd, timeout=timeout)

    # Parse pass/fail indicators
    output = result["stdout"] + "\n" + result["stderr"]
    passed = ("ok" in output.lower() or "passed" in output.lower()) and result["exit_code"] == 0
    failed = ("fail" in output.lower() or "error" in output.lower() or result["exit_code"] != 0) and not passed

    return {
        "test_target": test_target,
        "exit_code": result["exit_code"],
        "passed": passed and not failed,
        "output": output.strip(),
    }


# =====================================================================
# Phase 14: Function Calling Schemas (OpenAI & Nemotron format)
# =====================================================================

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a project file with optional line range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path from project root."},
                    "start_line": {"type": "integer", "description": "Starting line number (1-indexed)."},
                    "end_line": {"type": "integer", "description": "Ending line number (inclusive)."},
                    "with_line_numbers": {"type": "boolean", "description": "Whether to prefix line numbers."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace an exact target code snippet with new code in a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path from project root."},
                    "old_str": {"type": "string", "description": "Exact text to replace (must appear once)."},
                    "new_str": {"type": "string", "description": "New replacement text."},
                },
                "required": ["path", "old_str", "new_str"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create a new source, test, or config file within the project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path to create."},
                    "content": {"type": "string", "description": "Text content of the file."},
                    "overwrite": {"type": "boolean", "description": "Overwrite existing file if True."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Search for a keyword, function name, or pattern across all project files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Symbol or text pattern to search."},
                    "case_sensitive": {"type": "boolean", "description": "Match case if True."},
                    "max_matches": {"type": "integer", "description": "Maximum matches to return."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List all source files in the project or a specific subfolder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subpath": {"type": "string", "description": "Subdirectory to scan. Empty for root."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_project_summary",
            "description": "Retrieve project statistics: total lines of code, file counts, and extension breakdown.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember_fact",
            "description": "Permanently save a technical rule, convention, or fact in project memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Unique key identifier."},
                    "value": {"type": "string", "description": "Fact explanation or value."},
                    "category": {"type": "string", "description": "architecture, tech_stack, conventions, or general."},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_fact",
            "description": "Retrieve a specific remembered rule or fact by key.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Key identifier to recall."},
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_project_memory",
            "description": "Semantically search remembered facts and architectural decisions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language query."},
                    "top_k": {"type": "integer", "description": "Maximum memory items to return."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Safely execute a shell command in the project root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command string to run."},
                    "timeout": {"type": "integer", "description": "Max runtime in seconds."},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run the project test suite and return pass/fail report.",
            "parameters": {
                "type": "object",
                "properties": {
                    "test_target": {"type": "string", "description": "Target test directory or file."},
                },
            },
        },
    },
]


# Registry mapping tool names to python callable functions
TOOL_REGISTRY: Dict[str, Any] = {
    "read_file": read_file,
    "edit_file": edit_file,
    "create_file": create_file,
    "search_code": search_code,
    "list_files": list_files,
    "get_project_summary": get_project_summary,
    "get_project_tree": get_project_tree,
    "remember_fact": remember_fact,
    "recall_fact": recall_fact,
    "list_project_facts": list_project_facts,
    "record_project_decision": record_project_decision,
    "list_project_decisions": list_project_decisions,
    "search_project_memory": search_project_memory,
    "run_command": run_command,
    "run_tests": run_tests,
}


def get_tool_schemas() -> List[Dict[str, Any]]:
    """Return all available tool calling schemas."""
    return TOOL_SCHEMAS


def execute_tool(name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Dispatch and execute a tool by name with provided arguments.

    Returns:
        Structured result dict: {"tool": name, "success": bool, "result": Any, "error": Optional[str]}
    """
    arguments = arguments or {}
    tool_func = TOOL_REGISTRY.get(name)

    if not tool_func:
        return {
            "tool": name,
            "success": False,
            "result": None,
            "error": f"Unknown tool: '{name}'. Available tools: {list(TOOL_REGISTRY.keys())}",
        }

    try:
        result = tool_func(**arguments)
        return {
            "tool": name,
            "success": True,
            "result": result,
            "error": None,
        }
    except Exception as e:
        return {
            "tool": name,
            "success": False,
            "result": None,
            "error": str(e),
        }


def parse_tool_call(response_text: str) -> Optional[Dict[str, Any]]:
    """
    Extract a tool call from LLM response text.
    Handles:
      1. JSON code blocks: ```json {"name": "...", "arguments": {...}} ```
      2. XML-style tool tags: <tool_call>{"name": "...", "arguments": {...}}</tool_call>
      3. Bare JSON objects with "name" and "arguments" (or "tool" and "parameters").
    """
    text = response_text.strip()

    # Pattern 1: <tool_call> ... </tool_call>
    xml_match = re.search(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", text, re.DOTALL)
    if xml_match:
        try:
            return json.loads(xml_match.group(1))
        except json.JSONDecodeError:
            pass

    # Pattern 2: ```json ... ``` code block
    json_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_block:
        try:
            parsed = json.loads(json_block.group(1))
            if "name" in parsed or "tool" in parsed:
                return {
                    "name": parsed.get("name") or parsed.get("tool"),
                    "arguments": parsed.get("arguments") or parsed.get("parameters", {}),
                }
        except json.JSONDecodeError:
            pass

    # Pattern 3: Direct JSON string
    if text.startswith("{") and text.endswith("}"):
        try:
            parsed = json.loads(text)
            if "name" in parsed or "tool" in parsed:
                return {
                    "name": parsed.get("name") or parsed.get("tool"),
                    "arguments": parsed.get("arguments") or parsed.get("parameters", {}),
                }
        except json.JSONDecodeError:
            pass

    return None
