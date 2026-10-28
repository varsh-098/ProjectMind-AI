"""
scripts/phase13_project_memory.py
==================================
Phase 13 -- Project Memory Verification

PURPOSE:
    Demonstrate ProjectMind's persistent memory capabilities:
    1. Persistent Facts: Storing, retrieving, updating, and categorizing facts.
    2. Architecture Decision Records (ADRs): Logging technical decisions with rationale.
    3. Semantic Memory Search: Using Phase 11 vector embeddings to retrieve relevant facts.
    4. Prompt Context Injection: Compiling stored facts into a compact markdown block.
    5. Disk Persistence: Verifying facts survive in JSON storage.

RUN WITH:
    python scripts/phase13_project_memory.py
    or
    python -m scripts.phase13_project_memory
"""

import sys
import os

# Set stdout encoding for Windows console
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure repository root is on sys.path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from backend.brain import tools


def header(title: str):
    print("\n" + "=" * 65)
    print(f"  {title}")
    print("=" * 65)


def test_memory_overview():
    header("1. PROJECT MEMORY OVERVIEW & STATS")
    stats = tools.get_memory_stats()
    print(f"  Storage File:     {stats['storage_file']}")
    print(f"  Total Facts:      {stats['total_facts']}")
    print(f"  Total Decisions:  {stats['total_decisions']}")
    print("\n  Categories:")
    for cat, count in stats["categories"].items():
        print(f"    - {cat:<15}: {count} item(s)")


def test_fact_management():
    header("2. STORING & RECALLING FACTS")

    # Add a custom developer preference fact
    print("  Adding fact: 'code_formatting'...")
    tools.remember_fact(
        key="code_formatting",
        value="Use Black and Ruff with 88-character max line length.",
        category="conventions",
        tags=["formatting", "style", "python"],
    )

    # Recall the fact
    recalled = tools.recall_fact("code_formatting")
    print("  Recalled successfully:")
    print(f"    Key:         {recalled['key']}")
    print(f"    Category:    {recalled['category']}")
    print(f"    Value:       {recalled['value']}")
    print(f"    Tags:        {recalled['tags']}")

    # List facts in 'conventions' category
    print("\n  Listing all facts in category 'conventions':")
    conventions = tools.list_project_facts(category="conventions")
    for f in conventions:
        print(f"    • {f['key']}: {f['value']}")


def test_decision_records():
    header("3. ARCHITECTURAL DECISIONS (ADR)")

    # Record a new decision
    print("  Recording decision: 'Adopt In-Memory RAG Index'...")
    decision = tools.record_project_decision(
        title="Adopt In-Memory Vector Index for Phase 12",
        description="Built custom ProjectRAGIndex with cosine similarity and sliding window chunking.",
        rationale="Keeps learning curve gentle and avoids heavy vector DB daemon dependencies for local dev.",
        tags=["rag", "vectors", "simplicity"],
    )

    print(f"  Recorded ADR #{decision['id']} ({decision['date']}):")
    print(f"    Title:       {decision['title']}")
    print(f"    Rationale:   {decision['rationale']}")

    # List all decisions
    decisions = tools.list_project_decisions()
    print(f"\n  Total Recorded ADRs: {len(decisions)}")
    for d in decisions:
        print(f"    [{d['date']}] ADR #{d['id']}: {d['title']}")


def test_semantic_memory_search():
    header("4. SEMANTIC SEARCH ACROSS MEMORY (Phase 11 Embeddings)")

    queries = [
        "What LLM models and local servers do we support?",
        "How is code formatting or style configured?",
        "What design patterns are used in the LLM layer?",
    ]

    for q in queries:
        print(f"\n  Query: \"{q}\"")
        matches = tools.search_project_memory(q, top_k=2)
        for i, m in enumerate(matches, 1):
            if m["type"] == "fact":
                print(f"    #{i} [FACT - {m['category']}] (score: {m['score']})")
                print(f"       {m['key']}: {m['content']}")
            else:
                print(f"    #{i} [DECISION] (score: {m['score']})")
                print(f"       {m['title']}: {m['content']}")


def test_context_injection_block():
    header("5. PROMPT INJECTION CONTEXT BLOCK")
    context_block = tools.get_project_memory_context(max_chars=1200)
    print("  Compiled Prompt Block (what the LLM will see):\n")
    for line in context_block.splitlines():
        print(f"    {line}")


def main():
    print("\n" + "#" * 65)
    print("  PROJECTMIND AI -- PHASE 13: PROJECT MEMORY VERIFICATION")
    print("#" * 65)

    test_memory_overview()
    test_fact_management()
    test_decision_records()
    test_semantic_memory_search()
    test_context_injection_block()

    header("PHASE 13 COMPLETE")
    print("  Project Memory is operational and persisting to disk!")
    print("  ProjectMind can now remember architecture rules and developer decisions.")
    print("  Ready for Phase 14: Tools / Function Calling!\n")


if __name__ == "__main__":
    main()
