"""
backend/brain/rag.py
=====================
Retrieval-Augmented Generation (RAG) for ProjectMind AI.

WHAT RAG DOES:
    User: "Where is JWT authentication implemented?"

    WITHOUT RAG:
        LLM guesses based on general knowledge → wrong or generic answer.

    WITH RAG:
        1. Embed the user's question into a vector.
        2. Compare it against pre-indexed code chunk vectors.
        3. Retrieve the top 3-5 most similar chunks.
        4. Inject those chunks into the LLM prompt as context.
        5. LLM answers accurately using real project code.

PIPELINE:
    [INDEXING — done once or on file change]
    Project files → Scan → Chunk (with overlap) → Embed each chunk → Store in index

    [RETRIEVAL — done per user query]
    User question → Embed → Cosine similarity search → Top-K chunks
        → Build augmented prompt → LLM generates answer

WHY BUILD THIS OURSELVES?
    Frameworks like LangChain or LlamaIndex wrap this exact pipeline.
    Building it manually teaches every moving part so you can debug,
    optimize, or replace any step. This is what interviewers test.

INTERVIEW QUESTION:
    "What is RAG and why can't you just put all the code in the prompt?"

Answer:
    "RAG stands for Retrieval-Augmented Generation. An LLM has a finite
     context window (e.g. 4K–128K tokens). A real project can have millions
     of tokens of source code. You cannot fit it all in a single prompt.
     RAG solves this by embedding all code chunks into vectors, then for
     each query retrieving only the 3–5 most relevant chunks. This keeps
     the prompt small, focused, and within token limits while giving the
     LLM the exact context it needs to answer accurately."
"""

from typing import List, Dict, Any, Optional
from backend.brain import embeddings, tools


class ProjectRAGIndex:
    """
    In-memory vector index over chunked project source files.

    Stores (chunk_metadata, embedding_vector) pairs and supports
    semantic search via cosine similarity.
    """

    def __init__(
        self,
        chunk_max_lines: int = 35,
        chunk_overlap: int = 8,
    ):
        self.chunk_max_lines = chunk_max_lines
        self.chunk_overlap = chunk_overlap

        # The index: list of {"file", "start_line", "end_line", "text", "embedding"}
        self.chunks: List[Dict[str, Any]] = []
        self.indexed_files: List[str] = []

    # ------------------------------------------------------------------
    # STEP 1: Indexing — scan, chunk, embed, store
    # ------------------------------------------------------------------

    def index_file(self, filepath: str) -> int:
        """
        Read a single project file, chunk it, embed each chunk,
        and add the vectors to the index.

        Returns:
            Number of chunks generated from this file.
        """
        content = tools.read_file(filepath)
        file_chunks = embeddings.chunk_code(
            content=content,
            max_lines=self.chunk_max_lines,
            overlap_lines=self.chunk_overlap,
            file_path=filepath,
        )

        for chunk in file_chunks:
            chunk["embedding"] = embeddings.get_embedding(chunk["text"])
            self.chunks.append(chunk)

        if filepath not in self.indexed_files:
            self.indexed_files.append(filepath)

        return len(file_chunks)

    def index_directory(self, subpath: str = "") -> Dict[str, int]:
        """
        Index all source files in the project (or a subdirectory).

        Returns:
            Dict mapping filepath → number of chunks created.
        """
        files = tools.list_files(subpath=subpath)
        results = {}
        for f in files:
            path = f["path"]
            # Only index text source files
            ext = f.get("extension", "")
            if ext in (".py", ".js", ".ts", ".java", ".md", ".txt", ".yaml",
                        ".yml", ".toml", ".cfg", ".ini", ".sql", ".html",
                        ".css", ".sh", ".ps1", ".json"):
                try:
                    count = self.index_file(path)
                    results[path] = count
                except Exception:
                    results[path] = 0

        return results

    # ------------------------------------------------------------------
    # STEP 2: Retrieval — embed query, find top-K similar chunks
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.05,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve the top-K most relevant code chunks for a natural language query.

        Args:
            query: The user's question in plain English.
            top_k: Maximum number of chunks to return.
            min_score: Minimum cosine similarity threshold to include a chunk.

        Returns:
            List of chunk dicts sorted by similarity (highest first),
            each with an added "score" field.
        """
        if not self.chunks:
            return []

        query_vec = embeddings.get_embedding(query)

        scored = []
        for chunk in self.chunks:
            score = embeddings.cosine_similarity(query_vec, chunk["embedding"])
            if score >= min_score:
                scored.append({
                    "file": chunk["file"],
                    "start_line": chunk["start_line"],
                    "end_line": chunk["end_line"],
                    "text": chunk["text"],
                    "score": round(score, 4),
                })

        # Sort descending by similarity score
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    # ------------------------------------------------------------------
    # STEP 3: Augmented prompt construction
    # ------------------------------------------------------------------

    def build_augmented_prompt(
        self,
        user_question: str,
        top_k: int = 3,
        max_context_chars: int = 4000,
    ) -> str:
        """
        Build a prompt that injects retrieved code context before the user's question.

        This is the core of RAG — the LLM sees real project code alongside
        the question, enabling accurate, grounded answers.

        Args:
            user_question: The developer's question.
            top_k: Number of code chunks to retrieve and inject.
            max_context_chars: Character budget for injected context.

        Returns:
            The full augmented prompt string ready to send to the LLM.
        """
        retrieved = self.search(user_question, top_k=top_k)

        if not retrieved:
            # No relevant context found — fall back to plain question
            return user_question

        # Build context block from retrieved chunks
        context_parts = []
        total_chars = 0

        for chunk in retrieved:
            chunk_header = f"[{chunk['file']} lines {chunk['start_line']}-{chunk['end_line']}] (similarity: {chunk['score']})"
            chunk_block = f"{chunk_header}\n```\n{chunk['text']}\n```"

            if total_chars + len(chunk_block) > max_context_chars:
                break  # Stop if we'd exceed the character budget

            context_parts.append(chunk_block)
            total_chars += len(chunk_block)

        context_str = "\n\n".join(context_parts)

        augmented = (
            "The following code snippets are retrieved from the project codebase.\n"
            "Use them to answer the developer's question accurately.\n"
            "If the snippets do not contain enough information, say so.\n\n"
            "--- RETRIEVED PROJECT CODE ---\n\n"
            f"{context_str}\n\n"
            "--- END OF RETRIEVED CODE ---\n\n"
            f"Developer's question: {user_question}"
        )

        return augmented

    # ------------------------------------------------------------------
    # Index statistics
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        """Return summary statistics about the current index."""
        return {
            "total_chunks": len(self.chunks),
            "indexed_files": len(self.indexed_files),
            "files": self.indexed_files,
        }
"""
WHAT JUST HAPPENED?
    We built a complete RAG pipeline in ~200 lines with zero external
    vector database dependencies.

    Production systems use dedicated vector databases like ChromaDB,
    Pinecone, Weaviate, Qdrant, or FAISS for:
        - Persistent storage (survives restarts)
        - Approximate Nearest Neighbor (ANN) search (fast at scale)
        - Metadata filtering

    Our in-memory approach is perfect for learning and small projects.
    Replacing it with ChromaDB later requires changing only this file.
"""
