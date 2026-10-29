"""
backend/brain/file_manager.py
==============================
Core filesystem service for ProjectMind AI.

WHY THIS EXISTS:
    LLMs cannot assist with a project unless they can inspect it.
    This module gives ProjectMind safe, structured access to project files:
      1. Scanning the directory tree (ignoring .git, .env, __pycache__, binaries)
      2. Safe file reading (with path-traversal security & line-range slicing)
      3. Code search / grep across files
      4. Project overview and language statistics

SECURITY:
    - Path traversal attacks (e.g. '../../etc/passwd') are blocked via get_safe_path().
    - Sensitive files (.env, keys) are strictly ignored and never exposed.
    - Large files (> 1MB) and binary files are rejected.
"""

import os
from pathlib import Path
from typing import Any


class ProjectFileManager:
    """Manages secure inspection, reading, and searching of project files."""

    # Directories that should never be indexed or traversed
    IGNORED_DIRS = {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        ".venv",
        "venv",
        "env",
        ".idea",
        ".vscode",
        "dist",
        "build",
    }

    # Sensitive or unwanted file names
    IGNORED_FILES = {
        ".env",
        ".env.local",
        ".env.production",
        ".DS_Store",
        "thumbs.db",
    }

    # Binary / non-text extensions to skip
    BINARY_EXTENSIONS = {
        ".pyc", ".pyo", ".pyd", ".exe", ".dll", ".so", ".dylib",
        ".gguf", ".bin", ".pt", ".pth", ".onnx", ".pkl",
        ".zip", ".tar", ".gz", ".7z", ".rar",
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".svg",
        ".pdf", ".docx", ".xlsx", ".pptx",
        ".db", ".sqlite", ".sqlite3",
        ".mp3", ".mp4", ".wav", ".avi",
    }

    # Maximum allowed file size for reading into memory (1 MB)
    MAX_FILE_SIZE_BYTES = 1024 * 1024

    def __init__(self, root_path: str | Path | None = None):
        """
        Initialize the file manager.
        If root_path is not provided, resolves the repository root automatically.
        """
        if root_path is None:
            # Anchor to the ProjectMind-AI repo root
            current = Path(__file__).resolve().parent
            found_root = None
            while current != current.parent:
                if (current / ".git").exists():
                    found_root = current
                    break
                current = current.parent
            self.root_path = found_root or Path(__file__).resolve().parent.parent.parent
        else:
            self.root_path = Path(root_path).resolve()

    def is_ignored(self, path: Path) -> bool:
        """Check if a file or directory path should be ignored."""
        # Check if any parent or directory name matches IGNORED_DIRS
        for part in path.parts:
            if part in self.IGNORED_DIRS:
                return True

        # Check filename
        if path.name in self.IGNORED_FILES or path.name.startswith(".env"):
            return True

        # Check binary extensions
        if path.suffix.lower() in self.BINARY_EXTENSIONS:
            return True

        return False

    def get_safe_path(self, relative_path: str | Path) -> Path:
        """
        Resolve a path against root_path and verify it stays inside project boundaries.
        Raises PermissionError if path traversal is attempted.
        """
        clean_rel = str(relative_path).lstrip("/\\")
        target = (self.root_path / clean_rel).resolve()

        # Security check: must start with root_path
        if not str(target).startswith(str(self.root_path)):
            raise PermissionError(
                f"Security violation: path '{relative_path}' attempts to escape project root."
            )

        return target

    def list_files(self, subpath: str = "") -> list[dict[str, Any]]:
        """
        Recursively scan and return all non-ignored project files with metadata.
        """
        target_dir = self.get_safe_path(subpath)
        if not target_dir.is_dir():
            raise NotADirectoryError(f"'{subpath}' is not a directory.")

        results = []
        for root, dirs, files in os.walk(target_dir):
            # Prune ignored directories in-place so os.walk doesn't descend into them
            dirs[:] = [d for d in dirs if d not in self.IGNORED_DIRS]

            for file_name in files:
                file_path = Path(root) / file_name
                if self.is_ignored(file_path):
                    continue

                rel_path = file_path.relative_to(self.root_path).as_posix()
                try:
                    size = file_path.stat().st_size
                except OSError:
                    size = 0

                results.append({
                    "path": rel_path,
                    "name": file_name,
                    "extension": file_path.suffix.lower(),
                    "size_bytes": size,
                })

        return sorted(results, key=lambda x: x["path"])

    def get_tree(self, subpath: str = "", max_depth: int = 4) -> str:
        """
        Generate a human-readable ASCII directory tree (like tree /F).
        """
        target_dir = self.get_safe_path(subpath)
        if not target_dir.is_dir():
            raise NotADirectoryError(f"'{subpath}' is not a directory.")

        lines = [f"{target_dir.name or 'project-root'}/"]

        def _build_tree(current_dir: Path, prefix: str = "", depth: int = 1):
            if depth > max_depth:
                lines.append(f"{prefix}└── ... (max depth reached)")
                return

            try:
                entries = sorted(
                    [p for p in current_dir.iterdir() if not self.is_ignored(p)],
                    key=lambda p: (not p.is_dir(), p.name.lower()),
                )
            except PermissionError:
                return

            total = len(entries)
            for idx, entry in enumerate(entries):
                is_last = idx == total - 1
                connector = "└── " if is_last else "├── "
                sub_prefix = "    " if is_last else "│   "

                if entry.is_dir():
                    lines.append(f"{prefix}{connector}{entry.name}/")
                    _build_tree(entry, prefix + sub_prefix, depth + 1)
                else:
                    lines.append(f"{prefix}{connector}{entry.name}")

        _build_tree(target_dir, "", 1)
        return "\n".join(lines)

    def read_file(
        self,
        filepath: str,
        start_line: int = 1,
        end_line: int | None = None,
        with_line_numbers: bool = False,
    ) -> str:
        """
        Safely read a file's content or a slice of lines.
        """
        safe_file = self.get_safe_path(filepath)

        if not safe_file.exists():
            raise FileNotFoundError(f"File not found: '{filepath}'")

        if not safe_file.is_file():
            raise ValueError(f"Path is not a regular file: '{filepath}'")

        if self.is_ignored(safe_file):
            raise PermissionError(f"Access to file '{filepath}' is restricted.")

        # Check file size limit
        file_size = safe_file.stat().st_size
        if file_size > self.MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"File '{filepath}' exceeds size limit ({file_size} > {self.MAX_FILE_SIZE_BYTES} bytes)."
            )

        # Read text with UTF-8 and fallback replacement
        try:
            content = safe_file.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            raise IOError(f"Could not read '{filepath}': {e}")

        lines = content.splitlines()
        total_lines = len(lines)

        start_idx = max(1, start_line) - 1
        end_idx = total_lines if end_line is None else min(end_line, total_lines)

        selected_lines = lines[start_idx:end_idx]

        if with_line_numbers:
            numbered = [
                f"{i + start_idx + 1:4d} | {line}"
                for i, line in enumerate(selected_lines)
            ]
            return "\n".join(numbered)

        return "\n".join(selected_lines)

    def create_file(self, filepath: str | Path, content: str, overwrite: bool = False) -> dict[str, Any]:
        """
        Create a new file within the project boundaries.
        """
        target = self.get_safe_path(filepath)
        if self.is_ignored(target):
            raise PermissionError(f"Access to file '{filepath}' is restricted.")

        if target.exists() and not overwrite:
            raise FileExistsError(f"File '{filepath}' already exists. Set overwrite=True to replace.")

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

        return {
            "path": target.relative_to(self.root_path).as_posix(),
            "size_bytes": len(content.encode("utf-8")),
            "status": "created" if not target.exists() else "written",
        }

    def edit_file(self, filepath: str | Path, old_str: str, new_str: str) -> dict[str, Any]:
        """
        Safely replace an exact target substring within an existing project file.
        Enforces uniqueness to avoid unintended modifications.
        """
        target = self.get_safe_path(filepath)
        if self.is_ignored(target):
            raise PermissionError(f"Access to file '{filepath}' is restricted.")
        if not target.is_file():
            raise FileNotFoundError(f"File '{filepath}' does not exist.")

        content = target.read_text(encoding="utf-8", errors="replace")

        occurrences = content.count(old_str)
        if occurrences == 0:
            raise ValueError(f"Target string not found in '{filepath}'.")
        if occurrences > 1:
            raise ValueError(
                f"Target string appears {occurrences} times in '{filepath}'. "
                "Provide more surrounding context to uniquely identify the edit location."
            )

        updated_content = content.replace(old_str, new_str, 1)
        target.write_text(updated_content, encoding="utf-8")

        return {
            "path": target.relative_to(self.root_path).as_posix(),
            "occurrences_replaced": 1,
            "status": "success",
        }

    def search_code(
        self,
        query: str,
        case_sensitive: bool = False,
        max_matches: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Search for a query string across all text files in the project (Grep).
        """
        if not query or not query.strip():
            return []

        search_term = query if case_sensitive else query.lower()
        matches = []

        files = self.list_files()
        for f in files:
            safe_path = self.root_path / f["path"]
            try:
                content = safe_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            for line_no, line in enumerate(content.splitlines(), start=1):
                target = line if case_sensitive else line.lower()
                if search_term in target:
                    matches.append({
                        "file": f["path"],
                        "line_number": line_no,
                        "line_content": line.strip(),
                    })
                    if len(matches) >= max_matches:
                        return matches

        return matches

    def get_summary(self) -> dict[str, Any]:
        """
        Generate project statistics: file count, total lines, extension breakdown.
        """
        files = self.list_files()
        ext_counts: dict[str, int] = {}
        total_bytes = 0
        total_lines = 0

        for f in files:
            ext = f["extension"] or "(no extension)"
            ext_counts[ext] = ext_counts.get(ext, 0) + 1
            total_bytes += f["size_bytes"]

            # Count lines for common text files
            safe_path = self.root_path / f["path"]
            try:
                with open(safe_path, "r", encoding="utf-8", errors="replace") as fp:
                    total_lines += sum(1 for _ in fp)
            except Exception:
                pass

        # Sort extensions by count descending
        sorted_exts = dict(
            sorted(ext_counts.items(), key=lambda item: item[1], reverse=True)
        )

        return {
            "root": str(self.root_path),
            "total_files": len(files),
            "total_lines_of_code": total_lines,
            "total_size_kb": round(total_bytes / 1024, 2),
            "extensions": sorted_exts,
        }

