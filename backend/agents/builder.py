"""
backend/agents/builder.py
==========================
Phase 20 — Agent Builder & Dynamic Agent Registry.

PURPOSE:
    Provides a declarative factory to define, customize, validate, persist,
    and instantiate custom specialized AI agents without writing Python classes.

KEY COMPONENTS:
    1. AgentSpec: Schema defining an agent's configuration (supports Pydantic with fallback).
    2. CustomAgent: Subclass of BaseAgent configured dynamically from an AgentSpec.
    3. TEMPLATES: Ready-to-use blueprints (Documentation, Security, Refactor, DevOps).
    4. AgentBuilder: Factory, validator, and persistent registry managing all agents.
"""

import os
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from backend.agents.base_agent import BaseAgent
from backend.llm.base import BaseLLMProvider
from backend.brain import tools
from backend.brain.rag import ProjectRAGIndex


# =====================================================================
# 1. Declarative Agent Specification Schema
# =====================================================================

try:
    from pydantic import BaseModel, Field, field_validator

    class _BaseAgentSpec(BaseModel):
        name: str = Field(..., min_length=2, max_length=60)
        role: str = Field(..., min_length=3, max_length=100)
        description: str = Field(default="", max_length=300)
        system_instruction: str = Field(..., min_length=10)
        allowed_tools: List[str] = Field(default_factory=list)
        max_turns: int = Field(default=5, ge=1, le=15)
        temperature: float = Field(default=0.7, ge=0.0, le=1.5)
        enable_memory: bool = Field(default=True)
        enable_rag: bool = Field(default=True)
        tags: List[str] = Field(default_factory=list)
        created_at: Optional[str] = None
        is_template: bool = False

        @field_validator("name")
        @classmethod
        def validate_name_format(cls, v: str) -> str:
            clean = v.strip().lower().replace(" ", "_")
            if not clean.replace("_", "").isalnum():
                raise ValueError(f"Agent name '{v}' must be alphanumeric with underscores.")
            return clean

        @field_validator("allowed_tools")
        @classmethod
        def validate_allowed_tools(cls, v: List[str]) -> List[str]:
            valid_tools = set(tools.TOOL_REGISTRY.keys())
            invalid = [t for t in v if t not in valid_tools]
            if invalid:
                raise ValueError(
                    f"Unknown tool(s) requested: {invalid}. Available: {sorted(list(valid_tools))}"
                )
            return v

    AgentSpec = _BaseAgentSpec

except ImportError:
    # Standard-library fallback when pydantic is not installed
    class AgentSpec:
        """Standard-library fallback schema with identical validation interface."""

        def __init__(
            self,
            name: str,
            role: str,
            system_instruction: str,
            description: str = "",
            allowed_tools: Optional[List[str]] = None,
            max_turns: int = 5,
            temperature: float = 0.7,
            enable_memory: bool = True,
            enable_rag: bool = True,
            tags: Optional[List[str]] = None,
            created_at: Optional[str] = None,
            is_template: bool = False,
            **kwargs,
        ):
            # Validate name
            clean_name = name.strip().lower().replace(" ", "_")
            if not clean_name.replace("_", "").isalnum():
                raise ValueError(f"Agent name '{name}' must be alphanumeric with underscores.")
            self.name = clean_name

            # Validate role & system_instruction
            if not role or len(role.strip()) < 3:
                raise ValueError("Role must be at least 3 characters.")
            self.role = role.strip()

            if not system_instruction or len(system_instruction.strip()) < 10:
                raise ValueError("system_instruction must be at least 10 characters.")
            self.system_instruction = system_instruction.strip()

            self.description = description.strip()

            # Validate allowed_tools
            tools_list = allowed_tools or []
            valid_tools = set(tools.TOOL_REGISTRY.keys())
            invalid = [t for t in tools_list if t not in valid_tools]
            if invalid:
                raise ValueError(
                    f"Unknown tool(s) requested: {invalid}. Available: {sorted(list(valid_tools))}"
                )
            self.allowed_tools = tools_list

            self.max_turns = max(1, min(15, max_turns))
            self.temperature = max(0.0, min(1.5, temperature))
            self.enable_memory = enable_memory
            self.enable_rag = enable_rag
            self.tags = tags or []
            self.created_at = created_at
            self.is_template = is_template

        def model_dump(self) -> Dict[str, Any]:
            return {
                "name": self.name,
                "role": self.role,
                "description": self.description,
                "system_instruction": self.system_instruction,
                "allowed_tools": list(self.allowed_tools),
                "max_turns": self.max_turns,
                "temperature": self.temperature,
                "enable_memory": self.enable_memory,
                "enable_rag": self.enable_rag,
                "tags": list(self.tags),
                "created_at": self.created_at,
                "is_template": self.is_template,
            }

        def model_copy(self, update: Optional[Dict[str, Any]] = None) -> "AgentSpec":
            data = self.model_dump()
            if update:
                data.update(update)
            return AgentSpec(**data)


# =====================================================================
# 2. Dynamic Custom Agent Class
# =====================================================================

class CustomAgent(BaseAgent):
    """
    An agent configured entirely at runtime from an AgentSpec without
    requiring dedicated Python class boilerplate.
    """

    def __init__(
        self,
        spec: AgentSpec,
        llm_provider: Optional[BaseLLMProvider] = None,
    ):
        self.spec = spec
        super().__init__(
            name=spec.name,
            role=spec.role,
            system_instruction=spec.system_instruction,
            allowed_tools=spec.allowed_tools,
            llm_provider=llm_provider,
            max_turns=spec.max_turns,
        )

    def _build_system_prompt(self, include_memory: bool = True) -> str:
        """Honor spec.enable_memory setting when assembling prompt."""
        should_include_memory = include_memory and self.spec.enable_memory
        return super()._build_system_prompt(include_memory=should_include_memory)

    def run(
        self,
        user_prompt: str,
        rag_index: Optional[ProjectRAGIndex] = None,
        top_k_rag: int = 2,
    ) -> Dict[str, Any]:
        """Honor spec.enable_rag setting when executing ReAct loop."""
        effective_rag = rag_index if self.spec.enable_rag else None
        return super().run(
            user_prompt=user_prompt,
            rag_index=effective_rag,
            top_k_rag=top_k_rag,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize configuration back to dictionary."""
        return self.spec.model_dump()


# =====================================================================
# 3. Pre-Built Starter Templates
# =====================================================================

STARTER_TEMPLATES: Dict[str, AgentSpec] = {
    "documentation_agent": AgentSpec(
        name="documentation_agent",
        role="Senior Technical Writer & API Documenter",
        description="Creates clear documentation, docstrings, API references, and architecture guides.",
        system_instruction="""You are the Documentation Agent for ProjectMind AI.
Your purpose is to generate accurate, clear, and comprehensive documentation for the codebase.

RULES:
1. ALWAYS inspect existing source code using 'read_file' or 'search_code' before drafting docs.
2. Structure output cleanly with GitHub-flavored markdown, headings, tables, and code snippets.
3. For Python docstrings, use Google or Sphinx format with types and examples.
4. When saving documentation, call 'create_file' or 'edit_file' at appropriate paths (e.g. docs/ or README.md).
5. Never assume function signatures—verify them against the actual implementation.""",
        allowed_tools=[
            "read_file",
            "search_code",
            "list_files",
            "get_project_tree",
            "get_project_summary",
            "create_file",
            "edit_file",
            "recall_fact",
        ],
        max_turns=5,
        temperature=0.4,
        enable_memory=True,
        enable_rag=True,
        tags=["docs", "writing", "readme", "markdown", "architecture"],
        is_template=True,
    ),
    "security_auditor": AgentSpec(
        name="security_auditor",
        role="Application Security Specialist",
        description="Audits codebase for secrets, SQL injections, path traversals, and insecure execution patterns.",
        system_instruction="""You are the Security Auditor for ProjectMind AI.
Your objective is to identify security vulnerabilities, exposed secrets, and unsafe operations.

RULES:
1. Scan for dangerous patterns: hardcoded API keys, shell injection vulnerabilities, unvalidated paths, eval/exec.
2. Read suspicious files using 'read_file' to assess vulnerability severity (Critical, High, Medium, Low).
3. Check adherence to project security guardrails stored in persistent memory using 'recall_fact' or 'search_project_memory'.
4. Provide actionable remediation steps and secure code replacements for every identified issue.
5. Do NOT modify source files directly unless explicitly tasked—focus on thorough diagnostic reporting.""",
        allowed_tools=[
            "read_file",
            "search_code",
            "list_files",
            "get_project_summary",
            "recall_fact",
            "search_project_memory",
        ],
        max_turns=6,
        temperature=0.2,
        enable_memory=True,
        enable_rag=True,
        tags=["security", "audit", "vulnerability", "safety", "cve"],
        is_template=True,
    ),
    "refactoring_agent": AgentSpec(
        name="refactoring_agent",
        role="Software Quality & Refactoring Specialist",
        description="Cleans technical debt, modernizes syntax, adds type hints, and simplifies complex logic.",
        system_instruction="""You are the Refactoring Agent for ProjectMind AI.
Your purpose is to improve code readability, maintainability, and architectural structure without altering behavior.

RULES:
1. Analyze target modules using 'read_file' to understand dependencies and edge cases.
2. Keep edits focused and surgical using 'edit_file'. Do not rewrite unrelated methods.
3. Apply modern Python idioms: strict type annotations, context managers, list/dict comprehensions.
4. Verify non-regression: Always invoke 'run_tests' after applying changes to guarantee existing tests still pass.
5. Adhere to project conventions recorded in project memory (line length, naming, formatting).""",
        allowed_tools=[
            "read_file",
            "edit_file",
            "search_code",
            "list_files",
            "run_tests",
            "recall_fact",
        ],
        max_turns=6,
        temperature=0.3,
        enable_memory=True,
        enable_rag=True,
        tags=["refactor", "cleanup", "quality", "typing", "tests"],
        is_template=True,
    ),
    "devops_agent": AgentSpec(
        name="devops_agent",
        role="DevOps & Infrastructure Automation Engineer",
        description="Configures Dockerfiles, CI/CD pipelines, package dependencies, and environment configurations.",
        system_instruction="""You are the DevOps Agent for ProjectMind AI.
Your responsibility is to maintain build systems, container configurations, CI workflows, and environment setups.

RULES:
1. Inspect existing project structure and dependency definitions using 'list_files' and 'read_file'.
2. Generate standardized Dockerfiles, docker-compose.yml, GitHub Actions workflows, or build scripts via 'create_file'.
3. Validate commands using 'run_command' carefully and respect sandbox security constraints.
4. Never expose real credentials or API tokens in build scripts—use environment variable placeholders.
5. Document setup and run instructions clearly in deployment configs.""",
        allowed_tools=[
            "read_file",
            "create_file",
            "edit_file",
            "list_files",
            "get_project_summary",
            "run_command",
            "recall_fact",
        ],
        max_turns=5,
        temperature=0.3,
        enable_memory=True,
        enable_rag=False,
        tags=["devops", "docker", "ci-cd", "automation", "deploy"],
        is_template=True,
    ),
}


# =====================================================================
# 4. Agent Builder & Persistent Registry
# =====================================================================

class AgentBuilder:
    """
    Factory, validator, and persistent storage registry for custom AI agents.
    """

    def __init__(self, storage_path: Optional[str | Path] = None):
        if storage_path is None:
            data_dir = Path(__file__).resolve().parent / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.storage_file = data_dir / "custom_agents.json"
        else:
            self.storage_file = Path(storage_path).resolve()
            self.storage_file.parent.mkdir(parents=True, exist_ok=True)

        self._specs: Dict[str, AgentSpec] = {}
        self._instances: Dict[str, CustomAgent] = {}

        # 1. Load starter templates
        for name, spec in STARTER_TEMPLATES.items():
            self._specs[name] = spec.model_copy()

        # 2. Load user custom agents from disk
        self.load_from_disk()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load_from_disk(self) -> None:
        """Load stored custom agent specifications from JSON file."""
        if not self.storage_file.exists():
            return

        try:
            content = self.storage_file.read_text(encoding="utf-8")
            data = json.loads(content)
            for item in data.get("agents", []):
                spec = AgentSpec(**item)
                self._specs[spec.name] = spec
        except Exception:
            # Safe fallback if file is malformed
            pass

    def save_to_disk(self) -> None:
        """Serialize custom (non-template) agent specifications to disk."""
        custom_specs = [
            spec.model_dump()
            for spec in self._specs.values()
            if not spec.is_template
        ]
        data = {
            "version": "1.0",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "agents": custom_specs,
        }
        self.storage_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Creation & Registration
    # ------------------------------------------------------------------

    def build_agent(
        self,
        spec: AgentSpec | Dict[str, Any],
        llm_provider: Optional[BaseLLMProvider] = None,
        save: bool = True,
    ) -> CustomAgent:
        """
        Validate an AgentSpec, instantiate a CustomAgent, and optionally persist it.
        """
        if isinstance(spec, dict):
            validated_spec = AgentSpec(**spec)
        else:
            validated_spec = spec

        if not validated_spec.created_at:
            validated_spec.created_at = datetime.now(timezone.utc).isoformat()

        # Instantiate agent
        agent = CustomAgent(spec=validated_spec, llm_provider=llm_provider)

        # Store in registry
        self._specs[validated_spec.name] = validated_spec
        self._instances[validated_spec.name] = agent

        if save and not validated_spec.is_template:
            self.save_to_disk()

        return agent

    def build_from_template(
        self,
        template_name: str,
        name: str,
        role: Optional[str] = None,
        description: Optional[str] = None,
        extra_tools: Optional[List[str]] = None,
        llm_provider: Optional[BaseLLMProvider] = None,
        save: bool = True,
    ) -> CustomAgent:
        """
        Clone an existing template, customize fields, and instantiate the agent.
        """
        if template_name not in STARTER_TEMPLATES:
            raise KeyError(
                f"Template '{template_name}' not found. Available: {list(STARTER_TEMPLATES.keys())}"
            )

        template = STARTER_TEMPLATES[template_name]
        spec_dict = template.model_dump()

        spec_dict["name"] = name
        spec_dict["is_template"] = False
        if role:
            spec_dict["role"] = role
        if description:
            spec_dict["description"] = description
        if extra_tools:
            merged_tools = list(set(spec_dict["allowed_tools"] + extra_tools))
            spec_dict["allowed_tools"] = merged_tools

        return self.build_agent(spec=spec_dict, llm_provider=llm_provider, save=save)

    # ------------------------------------------------------------------
    # Query & Retrieval
    # ------------------------------------------------------------------

    def get_agent(
        self,
        name: str,
        llm_provider: Optional[BaseLLMProvider] = None,
    ) -> Optional[CustomAgent]:
        """Retrieve or instantiate an agent by name."""
        clean_name = name.strip().lower().replace(" ", "_")
        if clean_name in self._instances:
            return self._instances[clean_name]

        if clean_name in self._specs:
            spec = self._specs[clean_name]
            agent = CustomAgent(spec=spec, llm_provider=llm_provider)
            self._instances[clean_name] = agent
            return agent

        return None

    def get_spec(self, name: str) -> Optional[AgentSpec]:
        """Get specification metadata for an agent."""
        clean_name = name.strip().lower().replace(" ", "_")
        return self._specs.get(clean_name)

    def list_agents(self, include_templates: bool = True) -> List[Dict[str, Any]]:
        """List all registered agents and templates."""
        results = []
        for spec in self._specs.values():
            if not include_templates and spec.is_template:
                continue
            results.append({
                "name": spec.name,
                "role": spec.role,
                "description": spec.description,
                "allowed_tools": spec.allowed_tools,
                "max_turns": spec.max_turns,
                "is_template": spec.is_template,
                "tags": spec.tags,
                "created_at": spec.created_at,
            })
        return sorted(results, key=lambda x: (not x["is_template"], x["name"]))

    def list_templates(self) -> List[Dict[str, Any]]:
        """List pre-configured starter templates."""
        return [
            {
                "template_id": k,
                "name": v.name,
                "role": v.role,
                "description": v.description,
                "allowed_tools": v.allowed_tools,
                "tags": v.tags,
            }
            for k, v in STARTER_TEMPLATES.items()
        ]

    def delete_agent(self, name: str) -> bool:
        """
        Remove a custom agent from the registry and disk.
        Templates cannot be deleted.
        """
        clean_name = name.strip().lower().replace(" ", "_")
        if clean_name not in self._specs:
            return False

        if self._specs[clean_name].is_template:
            raise ValueError(f"Cannot delete built-in template '{clean_name}'.")

        del self._specs[clean_name]
        self._instances.pop(clean_name, None)
        self.save_to_disk()
        return True

    # ------------------------------------------------------------------
    # Supervisor Integration
    # ------------------------------------------------------------------

    def register_all_with_supervisor(self, supervisor: Any) -> int:
        """
        Dynamically register all custom agents into a Supervisor orchestrator instance.
        """
        count = 0
        for name, spec in self._specs.items():
            agent = self.get_agent(name, llm_provider=getattr(supervisor, "llm", None))
            if agent and hasattr(supervisor, "agent_registry"):
                supervisor.agent_registry[name] = agent
                count += 1
        return count


# Global default builder instance
default_agent_builder = AgentBuilder()
