"""
scripts/phase7_prompt_engineering.py
Phase 7 -- Prompt Engineering

PURPOSE:
    Write and verify the system prompts that will power each ProjectMind agent.
    We test them NOW, before building any agent infrastructure, so we know the
    prompts work before we depend on them in Phase 15-16.

    This phase produces: verified prompt strings that get used in Phase 15-16.
    It does NOT produce: agent classes, routing logic, or infrastructure.

RUN WITH:
    .venv\Scripts\python scripts\phase7_prompt_engineering.py

WHAT WE TEST:
    1. Base ProjectMind prompt      -- general assistant persona
    2. Coding Agent prompt          -- code understanding and fixing
    3. Review Agent prompt          -- structured code criticism
    4. JSON output enforcement      -- force structured output for the Supervisor
"""

import sys
import os
import json
import re

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.nemotron import ask_nemotron


def separator(title):
    print()
    print("=" * 65)
    print(f"  {title}")
    print("=" * 65)


def show(label, text, max_chars=500):
    """Print a labelled response, truncated for readability."""
    print(f"\n  [{label}]")
    text = text.strip()
    if len(text) > max_chars:
        print(f"  {text[:max_chars]}...")
    else:
        print(f"  {text}")


# =============================================================================
# THE PROMPTS
# =============================================================================
# These are the actual system instructions that will be used by each agent.
# We define them here as constants so they can later be imported by the
# agent classes in Phase 15-16.
#
# A good system prompt has four parts:
#   1. ROLE     -- who the model is
#   2. GOAL     -- what it is trying to achieve
#   3. RULES    -- hard constraints it must follow
#   4. FORMAT   -- how it must structure its output
# =============================================================================

# -----------------------------------------------------------------------------
# Prompt 1: Base ProjectMind Assistant
# -----------------------------------------------------------------------------
# Used by the /chat endpoint as the default persona.
# General-purpose but ProjectMind-aware.

PROJECTMIND_BASE_PROMPT = """You are ProjectMind AI, an expert software development assistant.

Your role:
- Help developers understand, design, and build software systems
- Give concise, technically accurate, and actionable answers
- Always prioritize clean architecture and engineering fundamentals over shortcuts

Rules:
- Never guess at facts you don't know -- say so clearly
- Keep answers focused -- do not pad with unnecessary explanation
- When discussing code, always specify the programming language
- Prefer simple solutions over complex ones

You are part of a project-aware AI workspace. The developer is building real software."""


# -----------------------------------------------------------------------------
# Prompt 2: Coding Agent
# -----------------------------------------------------------------------------
# Used by the Coding Agent in Phase 15.
# Focused on understanding and modifying code.

CODING_AGENT_PROMPT = """You are the ProjectMind Coding Agent.

Your role:
- Read and understand Python source code
- Identify and fix bugs when asked
- Implement new features cleanly and incrementally
- Explain every change you make and why

Rules:
- Only modify files you are explicitly asked about
- Write PEP-8 compliant Python code
- Do not introduce new dependencies without stating them explicitly
- If a requirement is ambiguous, state your assumption before implementing
- Always explain what you changed, not just what the final code looks like

Project context:
- Language: Python 3.11
- Framework: FastAPI
- The project is called ProjectMind AI
- Code style: clean, modular, well-commented"""


# -----------------------------------------------------------------------------
# Prompt 3: Review Agent
# -----------------------------------------------------------------------------
# Used by the Review Agent in Phase 16.
# Focused on structured, precise code criticism.
#
# KEY DESIGN DECISION: The Review Agent must output in a SPECIFIC FORMAT.
# This is critical for the Supervisor to parse results programmatically.
# We test this format enforcement here in Phase 7.

REVIEW_AGENT_PROMPT = """You are the ProjectMind Review Agent.

Your role:
- Review Python code critically and precisely
- Identify bugs, security vulnerabilities, and maintainability problems
- Suggest concrete, actionable fixes

Rules:
- Always cite the exact line number of each issue you find
- Rate every issue with one of these severities: CRITICAL / WARNING / SUGGESTION
- Never give vague feedback like "this could be improved" -- be specific
- Focus only on real problems, not stylistic preferences

Output format -- you MUST use exactly this structure for every issue:
[SEVERITY] Line N: <description of the problem>
Fix: <exactly what to change>

Example:
[CRITICAL] Line 14: SQL query uses string formatting, vulnerable to SQL injection.
Fix: Use parameterized queries with cursor.execute(query, (param,)) instead.

After listing all issues, add a one-line summary:
SUMMARY: Found N issues (X critical, Y warnings, Z suggestions)."""


# -----------------------------------------------------------------------------
# Prompt 4: JSON Output Prompt
# -----------------------------------------------------------------------------
# This is used when the Supervisor needs to PARSE the agent's output.
# Free-form text cannot be parsed reliably. JSON can.
#
# The challenge: LLMs love to add text before and after JSON.
# This prompt enforces clean JSON-only output.

JSON_OUTPUT_PROMPT = """You are a code analysis system that outputs structured JSON only.

Rules:
- Your entire response must be valid JSON
- Do not add any text before or after the JSON
- Do not add markdown code fences (no ```json)
- Do not add explanations, apologies, or commentary
- If you cannot complete the task, return: {"error": "reason"}

Output schema for code review:
{
  "issues": [
    {
      "severity": "CRITICAL" | "WARNING" | "SUGGESTION",
      "line": <integer>,
      "description": "<what is wrong>",
      "fix": "<what to change>"
    }
  ],
  "summary": {
    "total": <integer>,
    "critical": <integer>,
    "warnings": <integer>,
    "suggestions": <integer>
  }
}"""


# =============================================================================
# SAMPLE CODE FOR TESTING
# =============================================================================
# A small Python snippet with deliberate problems for the agents to find.

BUGGY_CODE = '''
def get_user(user_id):
    import sqlite3
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE id = " + str(user_id)
    cursor.execute(query)
    result = cursor.fetchone()
    return result

def calculate_average(numbers):
    total = 0
    for n in numbers:
        total = total + n
    average = total / len(numbers)
    return average

password = "admin123"
SECRET_KEY = "my-secret-key-do-not-share"
'''

# Problems in this code (what the agents should find):
# Line 5  - CRITICAL: SQL injection via string concatenation
# Line 9  - WARNING: database connection never closed (resource leak)
# Line 18 - WARNING: division by zero if numbers is empty
# Line 20 - CRITICAL: hardcoded password in source code
# Line 21 - CRITICAL: hardcoded secret key in source code


# =============================================================================
# EXPERIMENTS
# =============================================================================

separator("EXPERIMENT 1: Base ProjectMind Prompt")
print("  Testing: Does the base prompt give focused, professional responses?")
print("  Expected: Concise, technically accurate, no fluff")

question = "What is the difference between a process and a thread?"
answer, _, finish = ask_nemotron(question, max_tokens=400,
                                  temperature=0.4, system=PROJECTMIND_BASE_PROMPT)
show("ProjectMind AI response", answer)
print(f"\n  finish_reason: {finish}")


separator("EXPERIMENT 2: Coding Agent Prompt")
print("  Testing: Does the Coding Agent correctly understand and explain code?")
print("  Expected: Technical, specific, explains changes")

question = f"""Review this Python function and tell me if there are any problems:

```python
{BUGGY_CODE}
```

Focus only on the most critical issue. Name the line number."""

answer, _, finish = ask_nemotron(question, max_tokens=500,
                                  temperature=0.2, system=CODING_AGENT_PROMPT)
show("Coding Agent response", answer)
print(f"\n  finish_reason: {finish}")


separator("EXPERIMENT 3: Review Agent -- Structured Format")
print("  Testing: Does the Review Agent follow the exact output format?")
print("  Expected: [SEVERITY] Line N: description / Fix: ...")
print("  This format must be consistent for the Supervisor to parse it")

question = f"""Review this Python code and identify all issues:

```python
{BUGGY_CODE}
```"""

answer, usage, finish = ask_nemotron(question, max_tokens=2000,
                                      temperature=0.1, system=REVIEW_AGENT_PROMPT)
show("Review Agent response", answer, max_chars=800)
print(f"\n  Tokens used: {usage.get('total_tokens')}  |  finish_reason: {finish}")

# Check if the output follows the expected format
print("\n  FORMAT CHECK:")
has_severity = any(tag in answer for tag in ["[CRITICAL]", "[WARNING]", "[SUGGESTION]"])
has_fix = "Fix:" in answer
has_summary = "SUMMARY:" in answer
print(f"    Contains [SEVERITY] tags: {'PASS' if has_severity else 'FAIL'}")
print(f"    Contains Fix: lines:      {'PASS' if has_fix else 'FAIL'}")
print(f"    Contains SUMMARY line:    {'PASS' if has_summary else 'FAIL'}")


separator("EXPERIMENT 4: JSON Output Enforcement")
print("  Testing: Does the JSON prompt force clean, parseable JSON output?")
print("  Expected: Valid JSON only -- no text before/after")
print("  WHY THIS MATTERS: The Supervisor must parse agent output programmatically")

question = f"""Analyze this code and return results in the specified JSON schema:

```python
{BUGGY_CODE}
```"""

raw_answer, usage, finish = ask_nemotron(question, max_tokens=2000,
                                          temperature=0.0, system=JSON_OUTPUT_PROMPT)

show("Raw response from model", raw_answer, max_chars=600)

# Attempt to parse as JSON
print("\n  JSON PARSE CHECK:")
try:
    # Strip any accidental markdown fences if present
    clean = raw_answer.strip()
    clean = re.sub(r'^```json\s*', '', clean)
    clean = re.sub(r'\s*```$', '', clean)

    parsed = json.loads(clean)
    issue_count = len(parsed.get("issues", []))
    print(f"    PASS: Valid JSON parsed successfully")
    print(f"    Issues found: {issue_count}")
    print(f"    Summary: {parsed.get('summary', 'missing')}")
except json.JSONDecodeError as e:
    print(f"    FAIL: Could not parse JSON -- {e}")
    print(f"    This means the prompt needs adjustment before Phase 17 (Supervisor)")

print(f"\n  Tokens used: {usage.get('total_tokens')}  |  finish_reason: {finish}")


# =============================================================================
# SUMMARY
# =============================================================================

print()
print("=" * 65)
print("  Phase 7 COMPLETE -- Prompt Engineering Results")
print("=" * 65)
print()
print("  Prompts verified:")
print("    PROJECTMIND_BASE_PROMPT  -- general assistant")
print("    CODING_AGENT_PROMPT      -- code understanding and fixing")
print("    REVIEW_AGENT_PROMPT      -- structured code criticism")
print("    JSON_OUTPUT_PROMPT       -- machine-parseable output")
print()
print("  Next steps:")
print("    Phase 8  -- Groq API (second LLM backend)")
print("    Phase 15 -- Coding Agent uses CODING_AGENT_PROMPT")
print("    Phase 16 -- Review Agent uses REVIEW_AGENT_PROMPT + JSON_OUTPUT_PROMPT")
print("    Phase 17 -- Supervisor parses JSON from agents")
print()
