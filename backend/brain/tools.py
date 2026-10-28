"""
backend/brain/tools.py
=======================
Tools that AI agents use to inspect and interact with the project.

WHY TOOLS MATTER:
    Without tools, an agent can only THINK (generate text).
    With tools, an agent can ACT:
      - Read files and explore directories (Phase 10)
      - Access persistent facts & architectural memory (Phase 13)
      - Run searches and inspections across the codebase

Phase 10: File & Code Access Tools
Phase 13: Project Memory Tools
"""

from typing import Any, Optional, List
from backend.brain.file_manager import ProjectFileManager
from backend.brain.memory import ProjectMemoryManager

# Singleton instances for tool calls
_file_manager = ProjectFileManager()
_memory_manager = ProjectMemoryManager()


# =====================================================================
# Phase 10: File Access Tools
# =====================================================================

def read_file(
    path: str,
    start_line: int = 1,
    end_line: int | None = None,
    with_line_numbers: bool = False,
) -> str:
    """Read the contents of a project file."""
    return _file_manager.read_file(
        filepath=path,
        start_line=start_line,
        end_line=end_line,
        with_line_numbers=with_line_numbers,
    )


def list_files(subpath: str = "") -> list[dict[str, Any]]:
    """List all indexed source files in the project."""
    return _file_manager.list_files(subpath=subpath)


def get_project_tree(subpath: str = "", max_depth: int = 4) -> str:
    """Get an ASCII representation of the project's folder structure."""
    return _file_manager.get_tree(subpath=subpath, max_depth=max_depth)


def search_code(
    query: str,
    case_sensitive: bool = False,
    max_matches: int = 50,
) -> list[dict[str, Any]]:
    """Search for a text pattern or symbol across all project files (Grep)."""
    return _file_manager.search_code(
        query=query,
        case_sensitive=case_sensitive,
        max_matches=max_matches,
    )


def get_project_summary() -> dict[str, Any]:
    """Get overall statistics about the project."""
    return _file_manager.get_summary()


# =====================================================================
# Phase 13: Project Memory Tools
# =====================================================================

def remember_fact(
    key: str,
    value: str,
    category: str = "general",
    tags: Optional[List[str]] = None,
) -> dict[str, Any]:
    """
    Store a permanent fact in ProjectMind's persistent memory.

    Args:
        key: Unique identifier (e.g. 'auth_method').
        value: Fact description (e.g. 'JWT with HS256 algorithm').
        category: 'architecture', 'tech_stack', 'conventions', 'general'.
        tags: Optional list of keyword tags.
    """
    return _memory_manager.add_fact(key=key, value=value, category=category, tags=tags)


def recall_fact(key: str) -> Optional[dict[str, Any]]:
    """Retrieve a specific fact by key from persistent memory."""
    return _memory_manager.get_fact(key=key)


def list_project_facts(
    category: Optional[str] = None,
    tag: Optional[str] = None,
) -> list[dict[str, Any]]:
    """List stored facts, optionally filtered by category or tag."""
    return _memory_manager.list_facts(category=category, tag=tag)


def record_project_decision(
    title: str,
    description: str,
    rationale: str = "",
    tags: Optional[List[str]] = None,
) -> dict[str, Any]:
    """Record an architectural decision (ADR) in persistent memory."""
    return _memory_manager.record_decision(
        title=title,
        description=description,
        rationale=rationale,
        tags=tags,
    )


def list_project_decisions() -> list[dict[str, Any]]:
    """List all architectural decisions stored in memory."""
    return _memory_manager.list_decisions()


def search_project_memory(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Semantically search facts and decisions using vector similarity."""
    return _memory_manager.search_memory(query=query, top_k=top_k)


def get_project_memory_context(
    max_chars: int = 2500,
    category: Optional[str] = None,
) -> str:
    """Build a formatted memory context block ready to inject into the LLM prompt."""
    return _memory_manager.get_memory_context_block(max_chars=max_chars, category=category)


def get_memory_stats() -> dict[str, Any]:
    """Get stats about total facts, decisions, and categories."""
    return _memory_manager.stats()
