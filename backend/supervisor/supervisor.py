"""
backend/supervisor/supervisor.py
=================================
The Supervisor / Orchestrator — the brain of agent routing.

HOW IT WORKS:
    1. User sends a request: "Fix the login bug and run tests."
    2. Supervisor analyzes the request
    3. Determines which agents are needed:
       - Coding Agent (to fix the bug)
       - Testing Agent (to run tests)
    4. Orchestrates their execution (sequential or parallel)
    5. Combines results and returns to the user

IMPORTANT:
    The Supervisor does NOT activate every agent for every request.
    This is called DYNAMIC AGENT ROUTING.

    "Review my auth code."     → Review Agent only
    "Write a login function."  → Coding Agent only
    "Fix bug and run tests."   → Coding Agent + Testing Agent

Status: PLACEHOLDER — Phase 14+
"""
