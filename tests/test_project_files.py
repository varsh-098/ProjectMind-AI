"""
tests/test_project_files.py
============================
Automated unit tests for Phase 10: Project File Access.
Uses standard library unittest (runs with or without pytest installed).
"""

import unittest
from backend.brain.file_manager import ProjectFileManager
from backend.brain import tools


class TestProjectFileManager(unittest.TestCase):
    """Test suite for ProjectFileManager and agent tools."""

    def setUp(self):
        self.manager = ProjectFileManager()

    def test_safe_path_valid(self):
        """Valid relative paths inside project must resolve without error."""
        path = self.manager.get_safe_path("backend/config.py")
        self.assertTrue(path.exists())
        self.assertEqual(path.name, "config.py")

    def test_safe_path_traversal_blocked(self):
        """Directory traversal attempts must be blocked with PermissionError."""
        with self.assertRaises(PermissionError):
            self.manager.get_safe_path("../../Windows/System32/drivers/etc/hosts")

        with self.assertRaises(PermissionError):
            self.manager.get_safe_path("../../../etc/passwd")

    def test_env_file_ignored(self):
        """The .env file must be ignored to prevent secret leaks."""
        safe_path = self.manager.get_safe_path(".env")
        self.assertTrue(self.manager.is_ignored(safe_path))

    def test_list_files(self):
        """list_files() must return indexed source files and exclude secrets."""
        files = self.manager.list_files()
        self.assertGreater(len(files), 0)

        paths = [f["path"] for f in files]
        self.assertIn("backend/config.py", paths)
        self.assertNotIn(".env", paths)

    def test_read_file_with_line_range(self):
        """read_file() must support line range slicing and line numbers."""
        content = self.manager.read_file(
            filepath="backend/config.py",
            start_line=1,
            end_line=5,
            with_line_numbers=True,
        )
        lines = content.splitlines()
        self.assertEqual(len(lines), 5)
        self.assertTrue(lines[0].startswith("   1 |"))

    def test_read_env_blocked(self):
        """Direct attempt to read .env file must raise PermissionError."""
        with self.assertRaises(PermissionError):
            self.manager.read_file(".env")

    def test_search_code(self):
        """search_code() must find symbols across project files."""
        matches = self.manager.search_code("BaseLLMProvider", max_matches=10)
        self.assertGreater(len(matches), 0)
        self.assertTrue(any("backend/llm/base.py" in m["file"] for m in matches))

    def test_tools_wrapper_functions(self):
        """Verify high-level tools wrappers work cleanly."""
        summary = tools.get_project_summary()
        self.assertGreater(summary["total_files"], 0)
        self.assertGreater(summary["total_lines_of_code"], 0)
        self.assertIn(".py", summary["extensions"])

        tree = tools.get_project_tree(max_depth=2)
        self.assertIn("backend/", tree)


if __name__ == "__main__":
    unittest.main()
