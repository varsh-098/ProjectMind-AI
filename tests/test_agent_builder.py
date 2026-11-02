"""
tests/test_agent_builder.py
============================
Automated unit tests for Phase 20: Agent Builder.
Tests AgentSpec validation, CustomAgent execution, template cloning,
disk persistence, and dynamic Supervisor registration.
"""

import unittest
import tempfile
import shutil
from pathlib import Path

from backend.agents.builder import (
    AgentSpec,
    CustomAgent,
    AgentBuilder,
    STARTER_TEMPLATES,
)
from backend.supervisor.supervisor import Supervisor


class TestAgentBuilder(unittest.TestCase):
    """Test suite for Agent Builder and dynamic agent registration."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.storage_file = Path(self.test_dir) / "test_custom_agents.json"
        self.builder = AgentBuilder(storage_path=self.storage_file)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_spec_validation_valid(self):
        """Valid spec must normalize name and parse successfully."""
        spec = AgentSpec(
            name="Code Reviewer",
            role="Code Reviewer",
            description="Reviews code",
            system_instruction="You review code carefully and give feedback.",
            allowed_tools=["read_file", "search_code"],
        )
        self.assertEqual(spec.name, "code_reviewer")
        self.assertEqual(spec.allowed_tools, ["read_file", "search_code"])

    def test_spec_validation_invalid_tools(self):
        """Spec with non-existent tools must raise a ValueError."""
        with self.assertRaises(ValueError):
            AgentSpec(
                name="bad_agent",
                role="Tester",
                system_instruction="Do things",
                allowed_tools=["non_existent_tool_xyz"],
            )

    def test_starter_templates_exist(self):
        """All 4 core starter templates must be available in builder."""
        templates = self.builder.list_templates()
        template_ids = [t["template_id"] for t in templates]
        self.assertIn("documentation_agent", template_ids)
        self.assertIn("security_auditor", template_ids)
        self.assertIn("refactoring_agent", template_ids)
        self.assertIn("devops_agent", template_ids)

    def test_build_agent(self):
        """Must build and register a custom agent instance."""
        spec = AgentSpec(
            name="test_writer",
            role="Test Writer",
            description="Writes unit tests",
            system_instruction="Generate tests using pytest.",
            allowed_tools=["read_file", "create_file", "run_tests"],
            max_turns=4,
        )
        agent = self.builder.build_agent(spec=spec, save=True)
        self.assertIsInstance(agent, CustomAgent)
        self.assertEqual(agent.name, "test_writer")
        self.assertEqual(agent.max_turns, 4)

        # Check retrieval
        retrieved = self.builder.get_agent("test_writer")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "test_writer")

    def test_build_from_template(self):
        """Cloning a template must inherit tools while overriding fields."""
        agent = self.builder.build_from_template(
            template_name="documentation_agent",
            name="custom_docs_bot",
            role="Markdown Guru",
            extra_tools=["run_command"],
        )
        self.assertEqual(agent.name, "custom_docs_bot")
        self.assertEqual(agent.role, "Markdown Guru")
        self.assertIn("run_command", agent.allowed_tools)
        self.assertIn("read_file", agent.allowed_tools)

    def test_persistence_across_reloads(self):
        """Custom agents must persist to disk and reload in new builder."""
        spec = AgentSpec(
            name="persisted_agent",
            role="Persistent Role",
            system_instruction="Persist on disk.",
            allowed_tools=["read_file"],
        )
        self.builder.build_agent(spec=spec, save=True)

        # Create a new builder instance pointing to same file
        reloaded_builder = AgentBuilder(storage_path=self.storage_file)
        retrieved_spec = reloaded_builder.get_spec("persisted_agent")
        self.assertIsNotNone(retrieved_spec)
        self.assertEqual(retrieved_spec.name, "persisted_agent")

    def test_delete_agent(self):
        """Can delete user custom agents, but cannot delete templates."""
        spec = AgentSpec(
            name="temporary_agent",
            role="Temp",
            system_instruction="Temporary worker.",
            allowed_tools=["read_file"],
        )
        self.builder.build_agent(spec=spec, save=True)
        self.assertIsNotNone(self.builder.get_spec("temporary_agent"))

        # Delete it
        deleted = self.builder.delete_agent("temporary_agent")
        self.assertTrue(deleted)
        self.assertIsNone(self.builder.get_spec("temporary_agent"))

        # Attempt to delete template must raise ValueError
        with self.assertRaises(ValueError):
            self.builder.delete_agent("documentation_agent")

    def test_agent_run_offline_mode(self):
        """Custom agent must cleanly execute in offline / test mode."""
        spec = AgentSpec(
            name="offline_agent",
            role="Mock Agent",
            system_instruction="Work offline.",
            allowed_tools=["read_file"],
        )
        agent = self.builder.build_agent(spec=spec, save=False)
        agent.llm = None  # Explicitly set to None for offline test
        result = agent.run("Please inspect backend/config.py")
        self.assertTrue(result["success"])
        self.assertEqual(result["agent"], "offline_agent")
        self.assertIn("steps", result)

    def test_dynamic_supervisor_registration_and_routing(self):
        """Supervisor must route requests to newly registered custom agents."""
        supervisor = Supervisor(load_custom_agents=False)

        # Build custom agent
        spec = AgentSpec(
            name="api_documenter",
            role="API Doc Specialist",
            system_instruction="Generate API docs.",
            allowed_tools=["read_file"],
            tags=["api docs", "openapi"],
        )
        agent = self.builder.build_agent(spec=spec, save=False)

        # Register with supervisor
        supervisor.register_agent("api_documenter", agent)
        self.assertIn("api_documenter", supervisor.agent_registry)

        # Test routing by explicit name
        plan = supervisor.classify_intent("Please use api_documenter to document endpoints")
        self.assertEqual(plan["intent"], "CUSTOM")
        self.assertIn("api_documenter", plan["pipeline"])


if __name__ == "__main__":
    unittest.main()

