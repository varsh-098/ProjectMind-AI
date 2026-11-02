"""
backend/security/__init__.py
============================
Phase 24: Security & Sandboxing Module.

EXPORTS:
    - ToolPermission, PermissionDeniedError, PermissionChecker, permission_checker
    - WorkspaceSandbox, PathSecurityError, workspace_sandbox
    - CommandSanitizer, CommandSecurityError, command_sanitizer
    - CodeSecurityValidator, SecurityViolation, ValidationResult, ast_validator
"""

from backend.security.permissions import (
    ToolPermission,
    PermissionDeniedError,
    PermissionChecker,
    permission_checker,
    TOOL_PERMISSIONS,
    DEFAULT_ROLE_PERMISSIONS,
)
from backend.security.sandbox import (
    WorkspaceSandbox,
    PathSecurityError,
    CommandSanitizer,
    CommandSecurityError,
    workspace_sandbox,
    command_sanitizer,
)
from backend.security.ast_validator import (
    CodeSecurityValidator,
    SecurityViolation,
    ValidationResult,
    ast_validator,
)

__all__ = [
    "ToolPermission",
    "PermissionDeniedError",
    "PermissionChecker",
    "permission_checker",
    "TOOL_PERMISSIONS",
    "DEFAULT_ROLE_PERMISSIONS",
    "WorkspaceSandbox",
    "PathSecurityError",
    "CommandSanitizer",
    "CommandSecurityError",
    "workspace_sandbox",
    "command_sanitizer",
    "CodeSecurityValidator",
    "SecurityViolation",
    "ValidationResult",
    "ast_validator",
]

