"""
tests/test_memory.py
====================
Automated unit tests for Phase 13: Project Memory.
Tests ProjectMemoryManager, agent tools, persistence, and vector search.
"""

import unittest
import tempfile
import shutil
from pathlib import Path

from backend.brain.memory import ProjectMemoryManager
from backend.brain import tools


class TestProjectMemory(unittest.TestCase):
    """Test suite for Project Memory Manager."""

    def setUp(self):
        # Create an isolated temporary directory for test storage
        self.test_dir = tempfile.mkdtemp()
        self.storage_file = Path(self.test_dir) / "test_memory.json"
        self.memory = ProjectMemoryManager(storage_path=self.storage_file)

    def tearDown(self):
        # Clean up temporary directory
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_default_facts_seeded(self):
        """Newly created memory must seed baseline project facts."""
        self.assertGreater(len(self.memory.facts), 0)
        self.assertIsNotNone(self.memory.get_fact("backend_framework"))
        self.assertIsNotNone(self.memory.get_fact("llm_architecture"))

    def test_add_and_recall_fact(self):
        """Must correctly store and retrieve a new fact."""
        fact = self.memory.add_fact(
            key="database_type",
            value="PostgreSQL 16",
            category="tech_stack",
            tags=["database", "sql"],
        )
        self.assertEqual(fact["key"], "database_type")

        recalled = self.memory.get_fact("database_type")
        self.assertIsNotNone(recalled)
        self.assertEqual(recalled["value"], "PostgreSQL 16")
        self.assertIn("database", recalled["tags"])

    def test_filter_facts_by_category(self):
        """Must accurately filter facts by category."""
        tech_facts = self.memory.list_facts(category="tech_stack")
        self.assertTrue(all(f["category"] == "tech_stack" for f in tech_facts))

    def test_delete_fact(self):
        """Deleting a fact must remove it from memory."""
        self.memory.add_fact("temp_fact", "Temporary content", "general")
        self.assertIsNotNone(self.memory.get_fact("temp_fact"))

        deleted = self.memory.delete_fact("temp_fact")
        self.assertTrue(deleted)
        self.assertIsNone(self.memory.get_fact("temp_fact"))

    def test_record_decision(self):
        """Must record and increment architectural decisions (ADRs)."""
        initial_count = len(self.memory.decisions)
        decision = self.memory.record_decision(
            title="Use Pydantic v2 Settings",
            description="Centralize all environment variables in backend/config.py",
            rationale="Eliminates scattered os.getenv calls and provides validation",
            tags=["pydantic", "config"],
        )
        self.assertEqual(decision["id"], initial_count + 1)
        self.assertEqual(len(self.memory.decisions), initial_count + 1)

    def test_semantic_search(self):
        """Must return relevant facts/decisions using vector similarity."""
        matches = self.memory.search_memory("FastAPI framework and python", top_k=3)
        self.assertGreater(len(matches), 0)
        top_match = matches[0]
        self.assertIn("score", top_match)
        self.assertGreater(top_match["score"], 0.1)

    def test_context_block_generation(self):
        """Context block must contain formatted headers and facts."""
        block = self.memory.get_memory_context_block(max_chars=2000)
        self.assertIn("--- PROJECT MEMORY", block)
        self.assertIn("backend_framework", block)

    def test_disk_persistence(self):
        """Memory must persist across instance re-instantiation."""
        self.memory.add_fact("persistent_key", "This must survive reload", "conventions")

        # Create a fresh manager pointing to the exact same file
        reloaded_memory = ProjectMemoryManager(storage_path=self.storage_file)
        recalled = reloaded_memory.get_fact("persistent_key")
        self.assertIsNotNone(recalled)
        self.assertEqual(recalled["value"], "This must survive reload")


if __name__ == "__main__":
    unittest.main()

