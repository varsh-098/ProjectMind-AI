"""
tests/test_database.py
=======================
Automated unit tests for Phase 23: Database Persistence (MongoDB Atlas).
Tests session management, message history, agent execution run persistence,
and custom agent spec storage.
"""

import unittest
from backend.db.client import MongoDBManager
from backend.db import repository


class TestDatabaseRepository(unittest.TestCase):
    """Test suite for database repository CRUD operations."""

    def setUp(self):
        # Clear in-memory fallback store between tests
        repository._memory_store.clear()

    def test_session_lifecycle(self):
        """Test creating, reading, listing, and deleting conversation sessions."""
        session = repository.create_session(title="Refactoring Auth Service")
        self.assertIn("session_id", session)
        self.assertEqual(session["title"], "Refactoring Auth Service")

        # Retrieve session
        fetched = repository.get_session(session["session_id"])
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["title"], "Refactoring Auth Service")

        # List sessions
        sessions = repository.list_sessions()
        self.assertTrue(any(s["session_id"] == session["session_id"] for s in sessions))

        # Delete session
        deleted = repository.delete_session(session["session_id"])
        self.assertTrue(deleted)
        self.assertIsNone(repository.get_session(session["session_id"]))

    def test_message_history(self):
        """Test adding messages with model tier metadata and reading session history."""
        session = repository.create_session(title="Multi-Model Chat")
        sid = session["session_id"]

        msg1 = repository.add_message(
            session_id=sid,
            role="user",
            content="Can you optimize this query?",
        )
        msg2 = repository.add_message(
            session_id=sid,
            role="assistant",
            content="Here is the optimized indexing strategy...",
            tier_used="complex",
            model_used="gemini-2.5-pro",
            provider_used="gemini",
            latency_ms=340.5,
        )

        history = repository.get_session_messages(sid)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[1]["tier_used"], "complex")
        self.assertEqual(history[1]["model_used"], "gemini-2.5-pro")

    def test_record_agent_run(self):
        """Test recording Supervisor multi-agent orchestration runs and stage results."""
        run = repository.record_agent_run(
            task="Fix memory leak in RAG cache",
            intent="PIPELINE",
            stages=["coding", "testing"],
            results={
                "coding": {"changes": "Added LRU eviction policy"},
                "testing": {"passed": True, "tests_run": 5},
            },
            summary="Coding agent implemented LRU eviction; test agent verified 5/5 tests pass.",
            success=True,
            total_latency_ms=1250.0,
        )

        self.assertIn("run_id", run)
        fetched = repository.get_agent_run(run["run_id"])
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["intent"], "PIPELINE")
        self.assertEqual(fetched["stages"], ["coding", "testing"])
        self.assertEqual(fetched["results"]["testing"]["tests_run"], 5)

        runs = repository.list_agent_runs()
        self.assertTrue(any(r["run_id"] == run["run_id"] for r in runs))

    def test_custom_agent_persistence(self):
        """Test saving and retrieving custom agent specifications from database."""
        spec_data = {
            "name": "sql_tuner",
            "role": "Database Performance Specialist",
            "description": "Analyzes EXPLAIN plans and adds indexes.",
            "system_instruction": "You are a Postgres and Mongo tuning expert.",
            "allowed_tools": ["read_file", "search_code"],
            "model_tier": "complex",
        }

        saved = repository.save_custom_agent_spec(spec_data)
        self.assertEqual(saved["name"], "sql_tuner")

        fetched = repository.get_custom_agent_spec("sql_tuner")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["model_tier"], "complex")

        all_specs = repository.list_custom_agent_specs()
        self.assertTrue(any(s["name"] == "sql_tuner" for s in all_specs))

        deleted = repository.delete_custom_agent_spec("sql_tuner")
        self.assertTrue(deleted)
        self.assertIsNone(repository.get_custom_agent_spec("sql_tuner"))

    def test_client_unconfigured_ping(self):
        """Verify client reports unconfigured status when no URI is set."""
        manager = MongoDBManager(uri="", use_settings=False)
        res = manager.ping()
        self.assertEqual(res["status"], "unconfigured")
        self.assertFalse(res.get("connected", False))


if __name__ == "__main__":
    unittest.main()

