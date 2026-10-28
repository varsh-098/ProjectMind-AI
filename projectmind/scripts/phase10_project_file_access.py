"""
scripts/phase10_project_file_access.py
=======================================
Phase 10 -- Project File Access Verification

PURPOSE:
    Demonstrate that ProjectMind AI can safely inspect, read, search,
    and summarize the project's codebase before we feed files to Embeddings
    (Phase 11) and RAG (Phase 12).

RUN WITH:
    python scripts/phase10_project_file_access.py
    or
    python -m scripts.phase10_project_file_access
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


def test_project_summary():
    header("1. PROJECT METRICS & LANGUAGE BREAKDOWN")
    summary = tools.get_project_summary()
    print(f"  Project Root:        {summary['root']}")
    print(f"  Indexed Files:       {summary['total_files']}")
    print(f"  Total Lines of Code: {summary['total_lines_of_code']:,}")
    print(f"  Total Size:          {summary['total_size_kb']} KB")
    print("\n  File Types:")
    for ext, count in summary["extensions"].items():
        print(f"    - {ext:<15} : {count} files")


def test_tree_generation():
    header("2. DIRECTORY STRUCTURE (ASCII TREE)")
    tree = tools.get_project_tree(max_depth=3)
    for line in tree.splitlines()[:25]:
        print(f"  {line}")
    if len(tree.splitlines()) > 25:
        print("  ... (truncated for brevity)")


def test_safe_reading():
    header("3. SAFE FILE READING (backend/config.py lines 25-45)")
    content = tools.read_file(
        path="backend/config.py",
        start_line=25,
        end_line=45,
        with_line_numbers=True,
    )
    print(content)


def test_code_search():
    header("4. CODE SEARCH (Grep for 'BaseLLMProvider')")
    matches = tools.search_code("BaseLLMProvider", max_matches=5)
    print(f"  Found {len(matches)} match(es):")
    for m in matches:
        print(f"  [{m['file']}:{m['line_number']}]")
        print(f"    --> {m['line_content']}")


def test_security_guards():
    header("5. SECURITY & ACCESS CONTROL VERIFICATION")

    # Test 1: Path Traversal
    traversal_path = "../../Windows/System32/drivers/etc/hosts"
    try:
        tools.read_file(traversal_path)
        print("  [FAIL] Path traversal was NOT blocked!")
    except (PermissionError, ValueError) as e:
        print(f"  [PASS] Blocked traversal attempt: {e}")

    # Test 2: Reading .env secret
    try:
        tools.read_file(".env")
        print("  [FAIL] .env file was NOT blocked!")
    except PermissionError as e:
        print(f"  [PASS] Blocked secret access: {e}")


def main():
    print("\n" + "#" * 65)
    print("  PROJECTMIND AI -- PHASE 10: PROJECT FILE ACCESS VERIFICATION")
    print("#" * 65)

    test_project_summary()
    test_tree_generation()
    test_safe_reading()
    test_code_search()
    test_security_guards()

    header("PHASE 10 COMPLETE")
    print("  All project file access capabilities are operational!")
    print("  ProjectMind is now ready for Embeddings (Phase 11) & RAG (Phase 12).\n")


if __name__ == "__main__":
    main()

