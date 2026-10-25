"""
backend/brain/memory.py
========================
Project Memory — persistent knowledge about the project.

WHAT MEMORY STORES:
    - "Database is PostgreSQL"
    - "Authentication uses JWT"
    - "Redis is used for caching"
    - Architecture decisions
    - Developer preferences
    - Important project facts

DIFFERENCE FROM RAG:
    RAG:    "What information can I retrieve FROM the project files?"
    Memory: "What important facts has the system learned/remembered?"

    Both can be injected into the LLM prompt as context.

Status: PLACEHOLDER — Phase 10+
"""
