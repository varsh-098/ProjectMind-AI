"""
backend/agents/base_agent.py
=============================
Base class that all ProjectMind agents inherit from.

An agent is NOT just an LLM. An agent combines:
    - LLM (reasoning engine)
    - Instructions (what it should do)
    - Tools (what actions it can take)
    - Context (project knowledge from RAG/Memory)
    - State (conversation history, progress)

All specialized agents (Coding, Review, Testing) inherit from this
base and override the parts that make them unique.

Status: PLACEHOLDER — Phase 11+
"""
