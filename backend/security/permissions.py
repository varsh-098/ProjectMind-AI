"""
backend/security/permissions.py
================================
Phase 24: Role-Based Tool Permission Boundaries (Capability RBAC).

PURPOSE:
    Constrains AI agents by explicit capability tiers so that an agent cannot
    perform actions outside its assigned responsibility.
    For example:
      - ReviewAgent / SecurityAuditor: READ_ONLY (cannot write files or run commands).
      - CodingAgent: READ_ONLY + WORKSPACE_WRITE (cannot run shell commands).
      - TestingAgent: READ_ONLY + COMMAND_EXECUTE (can run test suites).
      - DevOpsAgent / CustomAgents: Configured per AgentSpec.
"""

from enum import Enum
from typing import Set, Dict, List, Optional, Any


class ToolPermission(str, Enum):
    """Granular tool capability tiers."""
    READ_ONLY = "read_only"
    WORKSPACE_WRITE = "workspace_write"
    COMMAND_EXECUTE = "command_execute"
    NETWORK_ACCESS = "network_access"
    ADMIN = "admin"


class PermissionDeniedError(PermissionError):
    """Raised when an agent attempts an action exceeding its assigned permissions."""
    def __init__(self, agent_name: str, tool_name: str, required_permission: ToolPermission):
        super().__init__(
            f"Permission Denied: Agent '{agent_name}' lacks required permission "
            f"'{required_permission.value}' to execute tool '{tool_name}'."
        )
        self.agent_name = agent_name
        self.tool_name = tool_name
        self.required_permission = required_permission


# =====================================================================
# Tool-to-Permission Mapping
# =====================================================================

TOOL_PERMISSIONS: Dict[str, ToolPermission] = {
    # Phase 10: File Inspection Tools
    "read_file": ToolPermission.READ_ONLY,
    "list_files": ToolPermission.READ_ONLY,
    "get_project_tree": ToolPermission.READ_ONLY,
    "search_code": ToolPermission.READ_ONLY,
    "get_project_summary": ToolPermission.READ_ONLY,

    # Phase 13: Project Memory Tools
    "recall_fact": ToolPermission.READ_ONLY,
    "list_project_facts": ToolPermission.READ_ONLY,
    "remember_fact": ToolPermission.WORKSPACE_WRITE,

    # Phase 14: Action Tools
    "create_file": ToolPermission.WORKSPACE_WRITE,
    "edit_file": ToolPermission.WORKSPACE_WRITE,
    "run_command": ToolPermission.COMMAND_EXECUTE,
    "run_tests": ToolPermission.COMMAND_EXECUTE,
}


# =====================================================================
# Default Role Permissions
# =====================================================================

DEFAULT_ROLE_PERMISSIONS: Dict[str, Set[ToolPermission]] = {
    "coding_agent": {
        ToolPermission.READ_ONLY,
        ToolPermission.WORKSPACE_WRITE,
    },
    "testing_agent": {
        ToolPermission.READ_ONLY,
        ToolPermission.COMMAND_EXECUTE,
    },
    "review_agent": {
        ToolPermission.READ_ONLY,
    },
    "documentation_agent": {
        ToolPermission.READ_ONLY,
        ToolPermission.WORKSPACE_WRITE,
    },
    "security_auditor": {
        ToolPermission.READ_ONLY,
    },
    "refactoring_agent": {
        ToolPermission.READ_ONLY,
        ToolPermission.WORKSPACE_WRITE,
    },
    "devops_agent": {
        ToolPermission.READ_ONLY,
        ToolPermission.WORKSPACE_WRITE,
        ToolPermission.COMMAND_EXECUTE,
    },
    "supervisor": {
        ToolPermission.READ_ONLY,
        ToolPermission.WORKSPACE_WRITE,
        ToolPermission.COMMAND_EXECUTE,
        ToolPermission.ADMIN,
    },
}


class PermissionChecker:
    """Evaluates agent permissions before executing tool calls."""

    def __init__(self, custom_permissions: Optional[Dict[str, Set[ToolPermission]]] = None):
        self._role_permissions: Dict[str, Set[ToolPermission]] = dict(DEFAULT_ROLE_PERMISSIONS)
        if custom_permissions:
            for role, perms in custom_permissions.items():
                self._role_permissions[role.lower()] = set(perms)

    def register_role_permissions(self, role: str, permissions: Set[ToolPermission]) -> None:
        """Register or update allowed permissions for an agent role or custom agent."""
        self._role_permissions[role.lower()] = set(permissions)

    def get_role_permissions(self, role: str) -> Set[ToolPermission]:
        """Get allowed permissions for a role, defaulting to READ_ONLY for unknown roles."""
        return self._role_permissions.get(role.lower(), {ToolPermission.READ_ONLY})

    def get_required_permission(self, tool_name: str) -> ToolPermission:
        """Get the required permission tier for a given tool name."""
        return TOOL_PERMISSIONS.get(tool_name, ToolPermission.WORKSPACE_WRITE)

    def is_permitted(self, agent_role: str, tool_name: str) -> bool:
        """Check if an agent role has permission to execute a specific tool."""
        required = self.get_required_permission(tool_name)
        allowed = self.get_role_permissions(agent_role)
        return (required in allowed) or (ToolPermission.ADMIN in allowed)

    def enforce_permission(self, agent_role: str, tool_name: str) -> None:
        """
        Enforce that an agent has the required permission for a tool.

        Raises:
            PermissionDeniedError: If the agent lacks permission.
        """
        if not self.is_permitted(agent_role, tool_name):
            required = self.get_required_permission(tool_name)
            raise PermissionDeniedError(
                agent_name=agent_role,
                tool_name=tool_name,
                required_permission=required,
            )


# Global singleton instance
permission_checker = PermissionChecker()
