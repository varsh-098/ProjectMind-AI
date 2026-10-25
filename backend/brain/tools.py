"""
backend/brain/tools.py
=======================
Tools that agents can use to perform actions.

EXAMPLES:
    read_file(path)      → Read a project file
    search_code(query)   → Search the codebase
    edit_file(path, ...) → Modify a file
    run_tests()          → Execute the test suite
    run_command(cmd)     → Run a shell command

WHY TOOLS MATTER:
    Without tools, an agent can only THINK (generate text).
    With tools, an agent can ACT (read files, run code, etc.).

    User: "Run the tests."
    Agent → run_tests() → test results → LLM → explains results

    Tools must eventually have authorization and security controls.

Status: PLACEHOLDER — Phase 11+
"""
