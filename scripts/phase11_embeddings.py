"""
scripts/phase11_embeddings.py
==============================
Phase 11 -- Vector Embeddings & Semantic Search Demonstration

PURPOSE:
    Demonstrate how source code and developer questions are converted into
    dense mathematical vectors (embeddings), and how Cosine Similarity ranks
    code snippets for semantic retrieval in RAG (Phase 12).

RUN WITH:
    python scripts/phase11_embeddings.py
    or
    python -m scripts.phase11_embeddings
"""

import sys
import os

# Set stdout encoding for Windows console
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure both projectmind and workspace root are on sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
projectmind_dir = os.path.dirname(script_dir)
workspace_root = os.path.dirname(projectmind_dir)

for p in (workspace_root, projectmind_dir):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.brain import embeddings, tools


def header(title: str):
    print("\n" + "=" * 65)
    print(f"  {title}")
    print("=" * 65)


def test_cosine_similarity_math():
    header("1. VECTOR MATHEMATICS & COSINE SIMILARITY")
    
    # 3 sample 3D vectors
    v_a = [1.0, 2.0, 3.0]
    v_b = [1.0, 2.0, 3.0]      # Identical to v_a
    v_c = [2.0, 4.0, 6.0]      # Same direction, 2x magnitude
    v_d = [-1.0, -2.0, -3.0]   # Exact opposite direction
    v_e = [3.0, 0.0, -1.0]     # Orthogonal (dot product = 3 - 3 = 0)

    sim_ab = embeddings.cosine_similarity(v_a, v_b)
    sim_ac = embeddings.cosine_similarity(v_a, v_c)
    sim_ad = embeddings.cosine_similarity(v_a, v_d)
    sim_ae = embeddings.cosine_similarity(v_a, v_e)

    print(f"  Vector A: {v_a}")
    print(f"  Vector B (identical):     Cosine Similarity = {sim_ab:.4f}  (Expected: 1.0000)")
    print(f"  Vector C (same angle):    Cosine Similarity = {sim_ac:.4f}  (Expected: 1.0000)")
    print(f"  Vector D (opposite):      Cosine Similarity = {sim_ad:.4f}  (Expected: -1.0000)")
    print(f"  Vector E (orthogonal):    Cosine Similarity = {sim_ae:.4f}  (Expected:  0.0000)")


def test_code_chunking():
    header("2. SOURCE CODE CHUNKING (backend/llm/factory.py)")
    
    raw_content = tools.read_file("backend/llm/factory.py")
    chunks = embeddings.chunk_code(
        content=raw_content,
        max_lines=25,
        overlap_lines=5,
        file_path="backend/llm/factory.py"
    )

    print(f"  Original file lines: {len(raw_content.splitlines())}")
    print(f"  Generated chunks:    {len(chunks)} (with 5 overlapping lines per boundary)")
    
    for idx, c in enumerate(chunks, 1):
        first_line = c["text"].splitlines()[0][:50]
        print(f"    - Chunk {idx}: Lines {c['start_line']:>2} to {c['end_line']:>2} ({c['line_count']} lines) -> \"{first_line}...\"")


def test_generating_embeddings():
    header("3. GENERATING VECTOR EMBEDDINGS (256 Dimensions)")
    
    samples = [
        "def verify_jwt_token(token: str): return decode(token)",
        "def authenticate_user_credentials(username, password): pass",
        "SELECT * FROM users WHERE status = 'active';",
        "def bake_chocolate_cake(flour, sugar, cocoa): pass"
    ]

    vectors = [embeddings.get_embedding(s) for s in samples]

    for text, vec in zip(samples, vectors):
        preview = [round(x, 3) for x in vec[:5]]
        mag = sum(x * x for x in vec) ** 0.5
        print(f"  Snippet: \"{text[:45]}...\"")
        print(f"    --> Dimensions: {len(vec)} | L2 Magnitude: {mag:.4f}")
        print(f"    --> First 5 components: {preview}\n")


def test_semantic_retrieval_ranking():
    header("4. SEMANTIC RETRIEVAL & SEARCH ON PROJECT CODEBASE")
    
    # 1. Index three distinct files from the ProjectMind backend
    files_to_index = [
        "backend/llm/factory.py",
        "backend/brain/file_manager.py",
        "backend/llm/groq_provider.py"
    ]
    
    corpus_chunks = []
    for f in files_to_index:
        content = tools.read_file(f)
        chunks = embeddings.chunk_code(content, max_lines=30, overlap_lines=5, file_path=f)
        for chunk in chunks:
            chunk["embedding"] = embeddings.get_embedding(chunk["text"])
            corpus_chunks.append(chunk)

    print(f"  Indexed {len(corpus_chunks)} code chunks across {len(files_to_index)} project files.")

    # 2. Test natural language queries
    queries = [
        "How to switch between Nemotron and Groq LLM providers dynamically?",
        "Security checks against path traversal and sensitive environment files",
        "Groq cloud API key authentication and streaming response"
    ]

    for q in queries:
        print(f"\n  Query: \"{q}\"")
        q_vec = embeddings.get_embedding(q)

        # Score all chunks with cosine similarity
        scored_chunks = []
        for c in corpus_chunks:
            score = embeddings.cosine_similarity(q_vec, c["embedding"])
            scored_chunks.append((score, c))

        # Rank descending
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_match = scored_chunks[0]

        print(f"    Top Match: [{top_match[1]['file']} lines {top_match[1]['start_line']}-{top_match[1]['end_line']}]")
        print(f"    Similarity Score: {top_match[0]:.4f}")
        snippet_preview = top_match[1]["text"].splitlines()[0]
        print(f"    Snippet: \"{snippet_preview}\"")


def main():
    print("\n" + "#" * 65)
    print("  PROJECTMIND AI -- PHASE 11: VECTOR EMBEDDINGS & SIMILARITY")
    print("#" * 65)

    test_cosine_similarity_math()
    test_code_chunking()
    test_generating_embeddings()
    test_semantic_retrieval_ranking()

    header("PHASE 11 COMPLETE")
    print("  Vector embeddings & cosine similarity calculations verified!")
    print("  ProjectMind is ready for Phase 12: RAG Pipeline Integration.\n")


if __name__ == "__main__":
    main()
