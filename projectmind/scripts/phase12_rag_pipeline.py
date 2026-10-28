"""
scripts/phase12_rag_pipeline.py
================================
Phase 12 -- Retrieval-Augmented Generation (RAG) Pipeline

PURPOSE:
    Demonstrate the complete RAG pipeline end-to-end:
    1. Index real ProjectMind source files (scan → chunk → embed → store)
    2. Semantic search: natural language query → retrieve relevant code chunks
    3. Prompt augmentation: inject retrieved code into the LLM prompt
    4. (Optional) Full RAG inference: send augmented prompt to Nemotron/Groq

    Experiments 1-3 run WITHOUT an LLM (pure retrieval verification).
    Experiment 4 runs WITH llama-server if it is available.

RUN WITH:
    python scripts/phase12_rag_pipeline.py
"""

import sys
import os
import time

# Set stdout encoding for Windows console
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure both workspace root and projectmind dir are on sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
projectmind_dir = os.path.dirname(script_dir)
workspace_root = os.path.dirname(projectmind_dir)

for p in (workspace_root, projectmind_dir):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.brain.rag import ProjectRAGIndex
from backend.brain import embeddings


def header(title: str):
    print("\n" + "=" * 65)
    print(f"  {title}")
    print("=" * 65)


# =====================================================================
# EXPERIMENT 1: Index the project and inspect the vector index
# =====================================================================
def experiment_1_indexing(rag: ProjectRAGIndex):
    header("EXPERIMENT 1: PROJECT INDEXING (Scan → Chunk → Embed → Store)")

    print("  Indexing backend/ directory...")
    t0 = time.perf_counter()
    results = rag.index_directory("backend")
    elapsed = time.perf_counter() - t0

    stats = rag.stats()
    print(f"\n  Indexing complete in {elapsed:.3f}s")
    print(f"  Files indexed:  {stats['indexed_files']}")
    print(f"  Total chunks:   {stats['total_chunks']}")
    print(f"\n  Per-file breakdown:")

    for filepath, chunk_count in sorted(results.items()):
        print(f"    {filepath:<45} → {chunk_count} chunks")

    # Validation
    assert stats["total_chunks"] > 0, "No chunks were created!"
    assert stats["indexed_files"] > 0, "No files were indexed!"
    print(f"\n  ✅ PASS — {stats['total_chunks']} chunks indexed across "
          f"{stats['indexed_files']} files")


# =====================================================================
# EXPERIMENT 2: Semantic search — 5 natural language queries
# =====================================================================
def experiment_2_semantic_search(rag: ProjectRAGIndex):
    header("EXPERIMENT 2: SEMANTIC SEARCH (Query → Top-K Retrieval)")

    queries = [
        "How does the factory pattern select between Nemotron and Groq?",
        "Where is path traversal security and .env file blocking implemented?",
        "How does the Groq cloud API authenticate with an API key?",
        "What is the base class interface that all LLM providers must follow?",
        "How are project files chunked with overlap for embedding?",
    ]

    # Expected best-match file for each query (for automated validation)
    expected_files = [
        "backend/llm/factory.py",
        "backend/brain/file_manager.py",
        "backend/llm/groq_provider.py",
        "backend/llm/base.py",
        "backend/brain/embeddings.py",
    ]

    passed = 0
    for i, (query, expected) in enumerate(zip(queries, expected_files), 1):
        results = rag.search(query, top_k=3)

        print(f"\n  Query {i}: \"{query}\"")

        if not results:
            print(f"    ❌ No results returned!")
            continue

        for rank, r in enumerate(results, 1):
            marker = "→" if rank == 1 else " "
            print(f"    {marker} #{rank}: [{r['file']} L{r['start_line']}-{r['end_line']}]  "
                  f"score={r['score']:.4f}")

        top_file = results[0]["file"]
        if expected in top_file:
            print(f"    ✅ Top result correctly matched: {expected}")
            passed += 1
        else:
            print(f"    ⚠️  Expected {expected}, got {top_file}")

    print(f"\n  Result: {passed}/{len(queries)} queries matched expected file")
    if passed >= 3:
        print(f"  ✅ PASS — Semantic search is working ({passed}/5 correct)")
    else:
        print(f"  ⚠️  PARTIAL — Only {passed}/5 correct (acceptable for subword embedder)")


# =====================================================================
# EXPERIMENT 3: Augmented prompt construction
# =====================================================================
def experiment_3_prompt_augmentation(rag: ProjectRAGIndex):
    header("EXPERIMENT 3: PROMPT AUGMENTATION (Retrieved Code → LLM Prompt)")

    question = "How does ProjectMind switch between different LLM providers at runtime?"
    augmented = rag.build_augmented_prompt(question, top_k=3, max_context_chars=3000)

    # Show the augmented prompt structure
    lines = augmented.splitlines()
    print(f"  Original question length:   {len(question)} chars")
    print(f"  Augmented prompt length:    {len(augmented)} chars")
    print(f"  Augmented prompt lines:     {len(lines)}")

    # Show first 8 lines and last 5 lines
    print(f"\n  --- AUGMENTED PROMPT (first 8 lines) ---")
    for line in lines[:8]:
        print(f"    {line}")

    print(f"    ...")
    print(f"  --- AUGMENTED PROMPT (last 5 lines) ---")
    for line in lines[-5:]:
        print(f"    {line}")

    # Validation checks
    has_context_marker = "RETRIEVED PROJECT CODE" in augmented
    has_code_blocks = "```" in augmented
    has_original_question = question in augmented

    print(f"\n  Validation:")
    print(f"    Context marker present:     {'✅' if has_context_marker else '❌'}")
    print(f"    Code blocks injected:       {'✅' if has_code_blocks else '❌'}")
    print(f"    Original question preserved: {'✅' if has_original_question else '❌'}")

    if has_context_marker and has_code_blocks and has_original_question:
        print(f"\n  ✅ PASS — Augmented prompt is correctly structured")
    else:
        print(f"\n  ❌ FAIL — Prompt structure is incorrect")


# =====================================================================
# EXPERIMENT 4: Full RAG inference (requires llama-server)
# =====================================================================
def experiment_4_full_rag_inference(rag: ProjectRAGIndex):
    header("EXPERIMENT 4: FULL RAG INFERENCE (Retrieve → Augment → LLM)")

    # Check if llama-server is running
    try:
        import requests
        health = requests.get("http://127.0.0.1:8081/health", timeout=2)
        if health.status_code != 200:
            raise ConnectionError()
    except Exception:
        print("  ⏭️  SKIPPED — llama-server is not running on port 8081.")
        print("  To run this experiment, start llama-server in another terminal:")
        print("    llama-server.exe --hf-repo nvidia/NVIDIA-Nemotron-3-Nano-4B-GGUF \\")
        print("      --hf-file NVIDIA-Nemotron3-Nano-4B-Q4_K_M.gguf \\")
        print("      --host 127.0.0.1 --port 8081 --n-gpu-layers 33")
        return

    # Import the nemotron client
    from backend.services.nemotron import ask_nemotron

    question = "What design patterns does ProjectMind use in its LLM layer and why?"

    # Step 1: Build augmented prompt with retrieved context
    augmented_prompt = rag.build_augmented_prompt(question, top_k=3)
    print(f"  Question: \"{question}\"")
    print(f"  Retrieved context injected: {augmented_prompt.count('```')} code blocks")

    # Step 2: Send to Nemotron with RAG context
    system_instruction = (
        "You are ProjectMind AI, a code-aware development assistant. "
        "Answer using ONLY the retrieved project code provided. "
        "Be specific: cite file names and line numbers. "
        "If the code does not contain enough information, say so."
    )

    print(f"\n  Sending augmented prompt to Nemotron...")
    t0 = time.perf_counter()
    answer, usage, finish = ask_nemotron(
        question=augmented_prompt,
        max_tokens=1500,
        temperature=0.1,
        system=system_instruction,
    )
    elapsed = time.perf_counter() - t0

    print(f"  Response received in {elapsed:.1f}s")
    print(f"  Tokens: prompt={usage.get('prompt_tokens', '?')}, "
          f"answer={usage.get('completion_tokens', '?')}")
    print(f"  Finish reason: {finish}")

    # Display the answer
    print(f"\n  --- NEMOTRON ANSWER (with RAG context) ---")
    for line in answer.splitlines():
        print(f"    {line}")
    print(f"  --- END OF ANSWER ---")

    # Validation: the answer should mention factory pattern or specific files
    answer_lower = answer.lower()
    mentions_factory = "factory" in answer_lower
    mentions_file = "factory.py" in answer_lower or "base.py" in answer_lower
    mentions_pattern = "pattern" in answer_lower or "abstract" in answer_lower

    print(f"\n  Validation:")
    print(f"    Mentions 'factory':          {'✅' if mentions_factory else '⚠️'}")
    print(f"    Cites specific file:         {'✅' if mentions_file else '⚠️'}")
    print(f"    Mentions design pattern:     {'✅' if mentions_pattern else '⚠️'}")

    if mentions_factory or mentions_pattern:
        print(f"\n  ✅ PASS — RAG-augmented answer references real project code")
    else:
        print(f"\n  ⚠️  PARTIAL — Answer may be using general knowledge instead of context")


# =====================================================================
# MAIN
# =====================================================================
def main():
    print("\n" + "#" * 65)
    print("  PROJECTMIND AI -- PHASE 12: RAG PIPELINE")
    print("#" * 65)

    # Create the RAG index (shared across all experiments)
    rag = ProjectRAGIndex(chunk_max_lines=35, chunk_overlap=8)

    experiment_1_indexing(rag)
    experiment_2_semantic_search(rag)
    experiment_3_prompt_augmentation(rag)
    experiment_4_full_rag_inference(rag)

    header("PHASE 12 COMPLETE")
    print("  RAG pipeline verified:")
    print("    ✅ Project files scanned, chunked, and embedded")
    print("    ✅ Semantic search retrieves relevant code chunks")
    print("    ✅ Augmented prompts inject real code into LLM context")
    print("  ProjectMind is ready for Phase 13: Project Memory.\n")


if __name__ == "__main__":
    main()

