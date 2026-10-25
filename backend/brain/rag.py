"""
backend/brain/rag.py
=====================
Retrieval-Augmented Generation (RAG) for project context.

WHAT RAG DOES:
    User: "Where is JWT authentication implemented?"

    RAG searches the project and retrieves relevant files:
        - AuthService.java
        - LoginController.java
        - JWTConfig.java

    These are injected into the LLM prompt so it has real
    project context, not just general knowledge.

PIPELINE:
    Project files → Parsing → Chunking → Embeddings
        → Vector DB → Semantic search → Reranking
        → Relevant context → LLM prompt

Status: PLACEHOLDER — Phase 9+
"""
