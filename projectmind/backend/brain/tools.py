"""
backend/brain/tools.py
=======================
Tools that AI agents use to inspect and interact with the project.

WHY TOOLS MATTER:
    Without tools, an agent can only THINK (generate text).
    With tools, an agent can ACT (read files, inspect code, run commands).

    User: "Where is the Groq provider defined and what methods does it have?"
    Agent → search_code("GroqProvider")
          → read_file("backend/llm/groq_provider.py", 1, 60)
          → LLM answers with 100% accuracy based on real code.

Phase 10 implements the core file & project access tools.
"""

from typing import Any
from backend.brain.file_manager import ProjectFileManager

# Singleton file manager instance for tool calls
_file_manager = ProjectFileManager()


def read_file(
    path: str,
    start_line: int = 1,
    end_line: int | None = None,
    with_line_numbers: bool = False,
) -> str:
    """
    Read the contents of a project file.

    Args:
        path: Relative path to the file from project root (e.g. 'backend/main.py').
        start_line: 1-indexed line to start reading from.
        end_line: 1-indexed line to stop reading at (inclusive). None reads to end.
        with_line_numbers: If True, prefixes each line with its line number.

    Returns:
        The text content of the requested file or line range.
    """
    return _file_manager.read_file(
        filepath=path,
        start_line=start_line,
        end_line=end_line,
        with_line_numbers=with_line_numbers,
    )


def list_files(subpath: str = "") -> list[dict[str, Any]]:
    """
    List all indexed source files in the project (excluding .git, .env, binaries).

    Args:
        subpath: Optional subfolder to scan (e.g. 'backend/llm'). Default is root.

    Returns:
        List of dictionaries with file metadata: path, name, extension, size_bytes.
    """
    return _file_manager.list_files(subpath=subpath)


def get_project_tree(subpath: str = "", max_depth: int = 4) -> str:
    """
    Get an ASCII representation of the project's folder structure.

    Args:
        subpath: Directory to build tree for.
        max_depth: Maximum folder depth to display.

    Returns:
        ASCII tree formatted string.
    """
    return _file_manager.get_tree(subpath=subpath, max_depth=max_depth)


def search_code(
    query: str,
    case_sensitive: bool = False,
    max_matches: int = 50,
) -> list[dict[str, Any]]:
    """
    Search for a text pattern or symbol across all project files.

    Args:
        query: String to search for (e.g. 'def get_llm_provider').
        case_sensitive: Whether to match case.
        max_matches: Cap on returned matches.

    Returns:
        List of matches: [{"file": "...", "line_number": 40, "line_content": "..."}]
    """
    return _file_manager.search_code(
        query=query,
        case_sensitive=case_sensitive,
        max_matches=max_matches,
    )


def get_project_summary() -> dict[str, Any]:
    """
    Get overall statistics about the project.

    Returns:
        Dict with total_files, total_lines_of_code, total_size_kb, and extensions.
    """
    return _file_manager.get_summary()
