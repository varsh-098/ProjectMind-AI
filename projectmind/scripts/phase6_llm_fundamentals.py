"""
scripts/phase6_llm_fundamentals.py
Phase 6 -- LLM Fundamentals experiments

Run with:  .venv\Scripts\python scripts\phase6_llm_fundamentals.py

This script demonstrates the key LLM parameters by calling Nemotron
directly and printing the real responses in readable form.
"""

import sys
import os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add project root to path so we can import our service
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json

ENDPOINT = "http://127.0.0.1:8081/v1/chat/completions"


def call_nemotron(question, max_tokens=300, temperature=0.7, system=None):
    """Send a request to Nemotron and return (answer, usage, finish_reason)."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": question})

    payload = {
        "model": "nemotron",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature
    }

    r = requests.post(ENDPOINT, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()

    answer       = data["choices"][0]["message"]["content"]
    finish       = data["choices"][0]["finish_reason"]
    usage        = data.get("usage", {})
    return answer, usage, finish


def separator(title):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


# -----------------------------------------------------------------------
# EXPERIMENT 1: Token awareness
# -----------------------------------------------------------------------
# We ask a short question and observe how few tokens it uses.
# Then we ask a long question and see the prompt token count rise.
# This makes tokens CONCRETE -- not abstract.
# -----------------------------------------------------------------------

separator("EXPERIMENT 1: Token counting")

short_q = "Hi."
long_q  = (
    "I am building a project-aware AI development workspace called ProjectMind. "
    "It will have RAG, memory, agents, a supervisor, and an LLM abstraction layer. "
    "Can you summarize what I just described in one sentence?"
)

for label, q in [("Short question", short_q), ("Long question", long_q)]:
    answer, usage, finish = call_nemotron(q, max_tokens=150)
    print(f"\n  [{label}]")
    print(f"  Q: {q[:80]}{'...' if len(q)>80 else ''}")
    print(f"  A: {answer.strip()[:200]}")
    print(f"  Prompt tokens: {usage.get('prompt_tokens')}  |  "
          f"Answer tokens: {usage.get('completion_tokens')}  |  "
          f"finish: {finish}")


# -----------------------------------------------------------------------
# EXPERIMENT 2: Temperature -- same question, three temperatures
# -----------------------------------------------------------------------
# Low temp = focused/deterministic
# High temp = creative/varied
# -----------------------------------------------------------------------

separator("EXPERIMENT 2: Temperature effect")

question = "Describe a software architect in one sentence."

for temp in [0.1, 0.8, 1.5]:
    answer, usage, finish = call_nemotron(question, max_tokens=200, temperature=temp)
    print(f"\n  temp={temp}  [{finish}]  ({usage.get('completion_tokens')} tokens)")
    print(f"  {answer.strip()}")


# -----------------------------------------------------------------------
# EXPERIMENT 3: System instructions / persona
# -----------------------------------------------------------------------
# The system message gives the model a persistent role.
# Without it: the model answers as a generic AI.
# With it: the model adopts the persona for the whole conversation.
# -----------------------------------------------------------------------

separator("EXPERIMENT 3: System instructions (persona)")

question = "What should I do first when starting a new software project?"

# Without system instructions
answer_plain, _, _ = call_nemotron(question, max_tokens=200, temperature=0.7)
print(f"\n  [No system instruction]")
print(f"  {answer_plain.strip()[:300]}")

# With a ProjectMind-specific system instruction
system_prompt = (
    "You are ProjectMind AI, an expert software development assistant "
    "that specializes in project architecture, clean code, and engineering best practices. "
    "Give concise, actionable advice. Always prioritize fundamentals over frameworks."
)
answer_pm, _, _ = call_nemotron(question, max_tokens=200, temperature=0.7, system=system_prompt)
print(f"\n  [With ProjectMind system instruction]")
print(f"  {answer_pm.strip()[:300]}")


# -----------------------------------------------------------------------
# EXPERIMENT 4: finish_reason -- stop vs length
# -----------------------------------------------------------------------
# "stop" means the model finished naturally.
# "length" means it hit the max_tokens ceiling -- answer was cut off.
# This is important: a truncated answer may be wrong or misleading.
# -----------------------------------------------------------------------

separator("EXPERIMENT 4: finish_reason (stop vs length)")

question = "What is Python? Answer in one sentence."

for max_t in [30, 300]:
    answer, usage, finish = call_nemotron(question, max_tokens=max_t, temperature=0.3)
    print(f"\n  max_tokens={max_t}  finish_reason='{finish}'")
    print(f"  Answer: {answer.strip()}")

print()
print("=" * 60)
print("  Phase 6 COMPLETE")
print("  Key takeaways:")
print("    - Tokens are the unit of cost and context budget")
print("    - Temperature controls randomness/creativity")
print("    - System instructions give the model a persistent role")
print("    - finish_reason tells you WHY the model stopped")
print("    - Nemotron uses internal <think> tokens before answering")
print("=" * 60)
print()
