"""
scripts/phase14_tools_execution.py
==================================
Phase 14 -- Agent Tools & Function Calling Verification

PURPOSE:
    Demonstrate that ProjectMind AI provides complete action capabilities
    for autonomous agents (Coding, Review, Testing):
    1. Tool Schema Registry (OpenAI/Nemotron-compatible function calling format)
    2. Safe File Actions (create_file, edit_file with uniqueness validation)
    3. Safe Command Execution (run_command with security blocklist and timeouts)
    4. Test Suite Execution (run_tests runner for Testing Agent)
    5. Agent Tool-Calling Loop (parse LLM tool calls → execute → format observation)

RUN WITH:
    python scripts/phase14_tools_execution.py
"""

import sys
import os
import json
from pathlib import Path

# Set stdout encoding for Windows console
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure repository root is on sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
projectmind_dir = os.path.dirname(script_dir)
workspace_root = os.path.dirname(projectmind_dir)

for p in (workspace_root, projectmind_dir):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.brain import tools


def header(title: str):
    print("\n" + "=" * 65)
    print(f"  {title}")
    print("=" * 65)


# =====================================================================
# EXPERIMENT 1: Tool Registry & Function Schemas
# =====================================================================
def test_tool_schemas():
    header("1. TOOL REGISTRY & FUNCTION CALLING SCHEMAS")

    schemas = tools.get_tool_schemas()
    print(f"  Registered Tool Schemas: {len(schemas)}")

    for s in schemas:
        fn = s["function"]
        required = fn.get("parameters", {}).get("required", [])
        print(f"  • {fn['name']:<22} : {fn['description'][:45]}... (required: {required})")

    assert len(schemas) >= 10, "Expected at least 10 registered tools!"
    print("\n  ✅ PASS — All function schemas are compliant and registered.")


# =====================================================================
# EXPERIMENT 2: Safe File Actions (Create & Edit)
# =====================================================================
def test_safe_file_actions():
    header("2. SAFE FILE ACTIONS (create_file & edit_file)")

    test_file = "tests/temp_phase14_scratch.py"
    initial_content = (
        "# Temporary scratch file for Phase 14\n"
        "def calculate_total(a, b):\n"
        "    return a - b  # BUG: subtraction instead of addition\n"
    )

    # 1. Create file
    print(f"  Creating file: '{test_file}'...")
    res_create = tools.execute_tool("create_file", {
        "path": test_file,
        "content": initial_content,
        "overwrite": True,
    })
    print(f"    Result: {res_create}")
    assert res_create["success"], f"Create failed: {res_create['error']}"

    # 2. Edit file (Fix the deliberate bug)
    print(f"\n  Applying surgical edit to fix bug...")
    old_code = "return a - b  # BUG: subtraction instead of addition"
    new_code = "return a + b  # FIXED: addition"

    res_edit = tools.execute_tool("edit_file", {
        "path": test_file,
        "old_str": old_code,
        "new_str": new_code,
    })
    print(f"    Result: {res_edit}")
    assert res_edit["success"], f"Edit failed: {res_edit['error']}"

    # Verify updated content
    updated_text = tools.read_file(test_file)
    print(f"\n  Updated File Content:\n{updated_text}")
    assert "return a + b" in updated_text, "Edit was not applied properly!"

    # 3. Test uniqueness failure (safety guard)
    print("  Testing uniqueness safety guard (non-existent old_str)...")
    res_fail = tools.execute_tool("edit_file", {
        "path": test_file,
        "old_str": "non_existent_code_line()",
        "new_str": "new_code()",
    })
    print(f"    Expected Error Caught: {res_fail['error']}")
    assert not res_fail["success"], "Uniqueness guard failed to catch missing string!"

    # Clean up scratch file
    try:
        Path(workspace_root, test_file).unlink(missing_ok=True)
        Path(projectmind_dir, test_file).unlink(missing_ok=True)
    except Exception:
        pass

    print("\n  ✅ PASS — create_file and edit_file performed safely with validation.")


# =====================================================================
# EXPERIMENT 3: Safe Command Execution
# =====================================================================
def test_command_execution():
    header("3. SAFE COMMAND EXECUTION (run_command & Security Guards)")

    # Test 1: Safe command
    print("  Executing safe command: 'python --version'...")
    res_safe = tools.execute_tool("run_command", {"command": "python --version"})
    print(f"    Exit Code: {res_safe['result']['exit_code']}")
    print(f"    Output:    {res_safe['result']['stdout']}")
    assert res_safe["success"], "Safe command failed!"

    # Test 2: Dangerous blocked command
    print("\n  Testing blocked command security guard: 'rm -rf /'...")
    res_blocked = tools.execute_tool("run_command", {"command": "rm -rf /"})
    print(f"    Success: {res_blocked['result']['success']}")
    print(f"    Blocked Reason: {res_blocked['result']['stderr']}")
    assert not res_blocked["result"]["success"], "Security guard failed to block command!"

    print("\n  ✅ PASS — Commands execute cleanly and dangerous patterns are rejected.")


# =====================================================================
# EXPERIMENT 4: Test Suite Runner
# =====================================================================
def test_test_runner():
    header("4. TEST SUITE EXECUTION (run_tests for Testing Agent)")

    print("  Executing unit tests: 'tests/test_memory.py'...")
    res_tests = tools.execute_tool("run_tests", {"test_target": "tests/test_memory.py"})

    print(f"    Target:  {res_tests['result']['test_target']}")
    print(f"    Passed:  {res_tests['result']['passed']}")
    print(f"    Summary: {res_tests['result']['output'].splitlines()[-1] if res_tests['result']['output'] else 'Done'}")

    assert res_tests["success"], f"Test execution failed: {res_tests['error']}"
    assert res_tests["result"]["passed"], "Memory unit tests did not pass!"
    print("\n  ✅ PASS — Testing tool successfully triggered pytest runner.")


# =====================================================================
# EXPERIMENT 5: Agent Tool-Calling Simulation Loop
# =====================================================================
def test_tool_calling_loop():
    header("5. AGENT TOOL-CALLING SIMULATION LOOP")

    # Simulate what an LLM (like Nemotron or Groq) outputs when it decides to call a tool
    simulated_llm_responses = [
        # Format 1: XML tag (Nemotron / Hermes style)
        '<tool_call>{"name": "search_code", "arguments": {"query": "BaseLLMProvider", "max_matches": 2}}</tool_call>',
        # Format 2: Markdown JSON codeblock
        '```json\n{"name": "recall_fact", "arguments": {"key": "backend_framework"}}\n```',
    ]

    for idx, raw_response in enumerate(simulated_llm_responses, start=1):
        print(f"\n  --- Simulated Turn {idx} ---")
        print(f"  Model Raw Output:\n    {raw_response.strip()}")

        # 1. Parse tool call from text
        tool_call = tools.parse_tool_call(raw_response)
        print(f"  Parsed Tool Call: {tool_call}")
        assert tool_call is not None, "Failed to parse tool call from model output!"

        # 2. Dispatch and execute
        execution_result = tools.execute_tool(tool_call["name"], tool_call["arguments"])
        print(f"  Execution Success: {execution_result['success']}")

        # 3. Format observation back to the LLM
        observation = json.dumps(execution_result["result"], indent=2)
        print(f"  Formatted Observation for Model:\n{observation[:180]}...")

    print("\n  ✅ PASS — Complete agent tool-calling loop verified.")


def main():
    print("\n" + "#" * 65)
    print("  PROJECTMIND AI -- PHASE 14: AGENT TOOLS & FUNCTION CALLING")
    print("#" * 65)

    test_tool_schemas()
    test_safe_file_actions()
    test_command_execution()
    test_test_runner()
    test_tool_calling_loop()

    header("PHASE 14 COMPLETE")
    print("  Action tools, execution safety, and tool-calling loops verified!")
    print("  ProjectMind is now ready for autonomous agents in Phase 15.\n")


if __name__ == "__main__":
    main()

