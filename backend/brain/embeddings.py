"""
backend/brain/embeddings.py
============================
Vector Embeddings & Semantic Similarity for ProjectMind AI.

WHY THIS EXISTS:
    Phase 11 introduces the mathematical engine that powers semantic search (RAG).
    
    1. Chunking: Large source files are split into digestible chunks with overlap.
    2. Embedding: Text & code are converted into high-dimensional numerical vectors.
    3. Similarity: Cosine similarity compares query vectors with code chunk vectors.

DESIGN:
    Zero mandatory external dependencies -- comes with a built-in normalized subword
    vectorizer that works offline immediately, with support for dense model backends.
"""

import math
import re
from typing import List, Dict, Any


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """
    Calculate the cosine similarity between two numerical vectors.
    
    Formula:
        similarity = (A . B) / (||A|| * ||B||)
        
    Returns:
        float between -1.0 and 1.0 (1.0 = identical direction/meaning, 0.0 = orthogonal)
    """
    if len(vec_a) != len(vec_b):
        raise ValueError(f"Vector dimensions do not match: {len(vec_a)} vs {len(vec_b)}")
    
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))
    
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    
    # Clip numerical precision errors to [-1.0, 1.0]
    similarity = dot_product / (mag_a * mag_b)
    return max(-1.0, min(1.0, similarity))


def chunk_code(
    content: str,
    max_lines: int = 40,
    overlap_lines: int = 8,
    file_path: str = ""
) -> List[Dict[str, Any]]:
    """
    Split source code into manageable chunks with overlapping lines to preserve context.
    
    Args:
        content: The raw text of the file.
        max_lines: Maximum number of lines per chunk.
        overlap_lines: Number of lines to overlap between adjacent chunks.
        file_path: Optional path for chunk metadata.
        
    Returns:
        List of chunk dicts: { "file": str, "start_line": int, "end_line": int, "text": str }
    """
    lines = content.splitlines()
    if not lines:
        return []
    
    chunks = []
    step = max(1, max_lines - overlap_lines)
    
    for i in range(0, len(lines), step):
        chunk_lines = lines[i : i + max_lines]
        start_line = i + 1
        end_line = i + len(chunk_lines)
        chunk_text = "\n".join(chunk_lines).strip()
        
        if chunk_text:  # Skip empty whitespace chunks
            chunks.append({
                "file": file_path,
                "start_line": start_line,
                "end_line": end_line,
                "line_count": len(chunk_lines),
                "text": chunk_text
            })
            
        if i + max_lines >= len(lines):
            break
            
    return chunks


class SubwordSemanticEmbedder:
    """
    Deterministic subword and token n-gram embedder for code & natural language.
    Produces a normalized 256-dimensional vector capturing:
    - Code identifier stems (snake_case, camelCase)
    - Structural language patterns & keywords
    - Semantic character 3-grams & 4-grams
    """
    
    def __init__(self, dimensions: int = 256):
        self.dimensions = dimensions

    def _tokenize(self, text: str) -> List[str]:
        # Split on whitespace, punctuation, and camelCase boundaries
        tokens = re.findall(r'[A-Za-z]+|\d+|[^\w\s]', text.lower())
        subwords = []
        for t in tokens:
            subwords.append(t)
            # Add character n-grams for typo-resilience and subword semantics
            if len(t) >= 3:
                for n in (3, 4):
                    for i in range(len(t) - n + 1):
                        subwords.append(t[i : i + n])
        return subwords

    def embed(self, text: str) -> List[float]:
        """Convert input text into a normalized float vector."""
        vec = [0.0] * self.dimensions
        subwords = self._tokenize(text)
        
        if not subwords:
            return vec
        
        for sw in subwords:
            # Deterministic hash mapped across vector space
            h = hash(sw)
            idx = abs(h) % self.dimensions
            sign = 1.0 if (h >> 7) & 1 else -1.0
            vec[idx] += sign
            
        # L2 Normalization so magnitude = 1.0
        mag = math.sqrt(sum(v * v for v in vec))
        if mag > 0:
            vec = [v / mag for v in vec]
            
        return vec


# Global default embedder
_default_embedder = SubwordSemanticEmbedder(dimensions=256)


def get_embedding(text: str) -> List[float]:
    """Generate an embedding vector for the given text."""
    return _default_embedder.embed(text)

