"""
backend/agents/__init__.py
===========================
ProjectMind AI Specialized Agents Package.

Exports:
    - BaseAgent: Core ReAct execution loop & context assembler
    - CodingAgent: Specialized in feature implementation & bug fixing
    - ReviewAgent: Code quality auditor & security reviewer
    - TestingAgent: Test suite designer & executor
    - AgentSpec: Declarative Pydantic schema for agent definitions
    - CustomAgent: Dynamic agent instantiated from an AgentSpec
    - AgentBuilder: Factory, registry & template manager
    - default_agent_builder: Global singleton builder instance
"""

from backend.agents.base_agent import BaseAgent
from backend.agents.coding_agent import CodingAgent
from backend.agents.review_agent import ReviewAgent
from backend.agents.testing_agent import TestingAgent
from backend.agents.builder import (
    AgentSpec,
    CustomAgent,
    AgentBuilder,
    default_agent_builder,
    STARTER_TEMPLATES,
)

__all__ = [
    "BaseAgent",
    "CodingAgent",
    "ReviewAgent",
    "TestingAgent",
    "AgentSpec",
    "CustomAgent",
    "AgentBuilder",
    "default_agent_builder",
    "STARTER_TEMPLATES",
]
